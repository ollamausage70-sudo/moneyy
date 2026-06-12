import json
import logging
from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Optional

from agent.brain import LLMBrain
from agent.database import DatabaseManager
from .message_bus import Message, MessageBus

logger = logging.getLogger("csuite.base")


class Authority(IntEnum):
    SUPPORT = 10
    OPERATIONS = 30
    STRATEGY = 50
    FINANCE = 60
    EXECUTIVE = 90
    FOUNDER = 100


class CLevelAgent(ABC):
    def __init__(
        self,
        name: str,
        title: str,
        authority: Authority,
        brain: LLMBrain,
        bus: MessageBus,
        db: DatabaseManager,
    ):
        self.name = name
        self.title = title
        self.authority = authority
        self.brain = brain
        self.bus = bus
        self.db = db
        self.logger = logging.getLogger("csuite.%s" % name)
        self.goals: list[dict] = []
        self.recent_decisions: list[dict] = []
        self.reports: list[dict] = []
        self.active = True

        self.bus.subscribe("agent:%s" % name, self._on_message)
        self.bus.subscribe("broadcast:strategy", self._on_strategy_broadcast)

    @abstractmethod
    async def think(self, context: dict) -> dict:
        pass

    def _on_message(self, message: Message):
        self.logger.info("RECV %s <- %s: %s", self.name, message.sender, message.subject)
        self.recent_decisions.append({
            "from": message.sender,
            "subject": message.subject,
            "body_preview": str(message.body)[:100],
        })
        if len(self.recent_decisions) > 50:
            self.recent_decisions = self.recent_decisions[-50:]

    def _on_strategy_broadcast(self, message: Message):
        self.logger.info("Strategy update from %s: %s", message.sender, message.subject)

    def send(self, recipient: str, subject: str, body: dict):
        msg = Message(sender=self.name, recipient=recipient, subject=subject, body=body)
        self.bus.publish(msg)

    def ask(self, recipient: str, subject: str, body: dict, timeout: float = 30.0) -> Optional[Message]:
        msg = Message(sender=self.name, recipient=recipient, subject=subject, body=body)
        return self.bus.ask(msg, timeout=timeout)

    def broadcast(self, subject: str, body: dict):
        self.bus.broadcast(self.name, subject, body)

    def save_decision(self, decision_type: str, context: dict, result: dict):
        self.db.save_csuite_decision(self.name, decision_type, context, result, 0)

    def set_goal(self, goal: str, priority: int = 5):
        self.goals.append({"goal": goal, "priority": priority, "status": "active"})
        self.goals.sort(key=lambda g: -g["priority"])
        self.goals = self.goals[:10]
        self.logger.info("New goal: %s (priority %d)", goal, priority)

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "authority": self.authority.name,
            "active": self.active,
            "goals": self.goals[:3],
            "recent_decisions": self.recent_decisions[-5:] if self.recent_decisions else [],
            "reports_count": len(self.reports),
        }

    def _llm_decide(self, prompt: str, system: Optional[str] = None) -> dict:
        try:
            result = self.brain.decide(prompt)
            return result
        except Exception as e:
            self.logger.error("LLM decision failed: %s", e)
            return {"decision": "error", "reason": str(e), "confidence": 0}
