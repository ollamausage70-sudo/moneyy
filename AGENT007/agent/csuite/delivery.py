import logging
from typing import Optional

from agent.brain import LLMBrain
from agent.database import DatabaseManager
from agent.skills.bounty_hunter import BountyHunterSkill
from .base import CLevelAgent, Authority
from .message_bus import MessageBus

logger = logging.getLogger("csuite.delivery")


class DeliveryAgent(CLevelAgent):
    def __init__(self, brain: LLMBrain, bus: MessageBus, db: DatabaseManager, bounty_hunter: BountyHunterSkill = None):
        super().__init__("Delivery", "Delivery Manager", Authority.OPERATIONS, brain, bus, db)
        self.bounty_hunter = bounty_hunter
        self.active_tasks: list[dict] = []
        self.completed: list[dict] = []
        self.set_goal("Execute tasks with 100% on-time delivery", 9)
        self.set_goal("Achieve >90% quality score on all deliverables", 8)

        self.bus.subscribe("task:execute", self._on_execute_task)
        self.bus.subscribe("qa:approved", self._on_qa_approved)
        self.bus.subscribe("qa:rejected", self._on_qa_rejected)

    def _on_execute_task(self, message):
        task_info = message.body
        self.active_tasks.append(task_info)
        self.logger.info("Received task for execution: %s", task_info.get("title", "?"))
        self.send("QA", "task:for_review", {
            "task_id": task_info.get("task_id"),
            "title": task_info.get("title"),
            "deliverable": task_info.get("deliverable", ""),
        })

    def _on_qa_approved(self, message):
        task_id = message.body.get("task_id")
        self.active_tasks = [t for t in self.active_tasks if t.get("task_id") != task_id]
        self.completed.append({"task_id": task_id, "status": "approved"})
        self.logger.info("Task approved by QA: %s", task_id)

    def _on_qa_rejected(self, message):
        task_id = message.body.get("task_id")
        feedback = message.body.get("feedback", "")
        self.logger.warning("Task rejected by QA: %s — %s", task_id, feedback)
        for t in self.active_tasks:
            if t.get("task_id") == task_id:
                t["retries"] = t.get("retries", 0) + 1
                if t["retries"] < 3:
                    self._rework_task(t, feedback)

    def _rework_task(self, task: dict, feedback: str):
        self.logger.info("Reworking task: %s (attempt %d)", task.get("title"), task.get("retries"))
        if self.bounty_hunter:
            from agent.skills.base import Task as BTask
            btask = BTask(
                id=task.get("task_id", ""),
                title=task.get("title", ""),
                description=task.get("description", ""),
                reward=float(task.get("reward", 0)),
                reward_currency="USDC",
                source=task.get("source", ""),
                requirements=task.get("requirements", ""),
            )
            draft = self.bounty_hunter.trainer.fix_deliverable(
                {"title": btask.title, "requirements": btask.requirements},
                task.get("deliverable", ""), feedback,
            )
            self.send("QA", "task:for_review", {
                "task_id": task.get("task_id"),
                "title": task.get("title"),
                "deliverable": draft,
                "is_rework": True,
            })

    async def think(self, context: dict) -> dict:
        prompt = (
            "As Delivery Manager for AGENT007, analyze delivery operations:\n\n"
            "Active tasks: %d\n"
            "Completed: %d\n"
            "Reworks: %d\n\n"
            "Are we delivering on time? Any bottlenecks? "
            "Respond JSON with: status (green/yellow/red), "
            "bottlenecks (list), recommendations (str)." % (
                len(self.active_tasks),
                len(self.completed),
                sum(1 for t in self.active_tasks if t.get("retries", 0) > 0),
            )
        )
        result = self._llm_decide(prompt)
        self.save_decision("delivery_analysis", context, result)
        return result

    def get_delivery_summary(self) -> dict:
        return {
            "active": len(self.active_tasks),
            "completed": len(self.completed),
            "active_tasks": [{"title": t.get("title", "?")[:30], "retries": t.get("retries", 0)} for t in self.active_tasks],
        }
