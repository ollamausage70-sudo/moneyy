import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger("csuite.bus")


class Priority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Message:
    sender: str
    recipient: str
    subject: str
    body: dict
    priority: Priority = Priority.NORMAL
    reply_to: Optional[str] = None
    id: str = field(default_factory=lambda: "msg_%d_%d" % (time.time_ns(), id(asyncio)))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sender": self.sender,
            "recipient": self.recipient,
            "subject": self.subject,
            "body": self.body,
            "priority": self.priority.name,
            "reply_to": self.reply_to,
            "timestamp": datetime.utcnow().isoformat(),
        }


class MessageBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        self._history: list[Message] = []
        self._history_max = 500

    def subscribe(self, subject: str, callback: Callable):
        if subject not in self._subscribers:
            self._subscribers[subject] = []
        self._subscribers[subject].append(callback)
        logger.debug("Subscribed %s to '%s'", getattr(callback, "__name__", callback), subject)

    def subscribe_agent(self, agent_name: str, callback: Callable):
        self.subscribe("agent:%s" % agent_name, callback)

    def publish(self, message: Message):
        self._history.append(message)
        if len(self._history) > self._history_max:
            self._history = self._history[-self._history_max:]

        subjects = [
            message.subject,
            message.recipient,
            "agent:%s" % message.recipient,
        ]
        for subject in subjects:
            if not subject:
                continue
            callbacks = self._subscribers.get(subject, [])
            for cb in callbacks:
                try:
                    cb(message)
                except Exception as e:
                    logger.error("Bus callback error for '%s': %s", subject, e)

        logger.info("BUS: %s -> %s [%s]", message.sender, message.recipient, message.subject)

    def ask(self, message: Message, timeout: float = 30.0) -> Optional[Message]:
        result_container = []

        def reply_handler(reply: Message):
            if reply.reply_to == message.id:
                result_container.append(reply)

        self.subscribe("reply:%s" % message.id, reply_handler)
        self.publish(message)

        deadline = time.time() + timeout
        while time.time() < deadline:
            if result_container:
                return result_container[0]
            time.sleep(0.1)
        logger.warning("Bus ask timeout for %s -> %s [%s]", message.sender, message.recipient, message.subject)
        return None

    def reply(self, original: Message, body: dict):
        reply = Message(
            sender=original.recipient,
            recipient=original.sender,
            subject="reply:%s" % original.id,
            body=body,
            reply_to=original.id,
        )
        self.publish(reply)

    def broadcast(self, sender: str, subject: str, body: dict):
        msg = Message(sender=sender, recipient="*", subject=subject, body=body)
        self.publish(msg)

    def get_history(self, limit: int = 50) -> list:
        return [m.to_dict() for m in self._history[-limit:]]
