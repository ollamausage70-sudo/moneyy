import logging
from datetime import datetime
from typing import Optional

from agent.brain import LLMBrain
from agent.database import DatabaseManager
from .base import CLevelAgent, Authority
from .message_bus import MessageBus

logger = logging.getLogger("csuite.coo")


class COOAgent(CLevelAgent):
    def __init__(self, brain: LLMBrain, bus: MessageBus, db: DatabaseManager):
        super().__init__("COO", "Chief Operations Officer", Authority.EXECUTIVE, brain, bus, db)
        self.operations = {
            "tasks_in_progress": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "active_deliveries": [],
            "queue_depth": 0,
        }
        self.set_goal("Zero failed task executions", 9)
        self.set_goal("Maximize task throughput", 8)
        self.set_goal("Maintain >80% task completion rate", 7)

        self.bus.subscribe("task:assigned", self._on_task_assigned)
        self.bus.subscribe("task:completed", self._on_task_completed)
        self.bus.subscribe("task:failed", self._on_task_failed)
        self.bus.subscribe("broadcast:strategy", self._on_strategy)

    def _on_task_assigned(self, message):
        self.operations["tasks_in_progress"] += 1
        self.operations["queue_depth"] += 1
        self.operations["active_deliveries"].append({
            "task_id": message.body.get("task_id"),
            "title": message.body.get("title", "?"),
            "assigned_at": datetime.utcnow().isoformat(),
        })
        self.logger.info("Task assigned: %s", message.body.get("title", "?"))

    def _on_task_completed(self, message):
        self.operations["tasks_completed"] += 1
        self.operations["tasks_in_progress"] = max(0, self.operations["tasks_in_progress"] - 1)
        self.operations["queue_depth"] = max(0, self.operations["queue_depth"] - 1)
        self.operations["active_deliveries"] = [
            d for d in self.operations["active_deliveries"]
            if d["task_id"] != message.body.get("task_id")
        ]
        self.logger.info("Task completed: %s", message.body.get("title", "?"))

    def _on_task_failed(self, message):
        self.operations["tasks_failed"] += 1
        self.operations["tasks_in_progress"] = max(0, self.operations["tasks_in_progress"] - 1)
        self.logger.warning("Task failed: %s — %s", message.body.get("title", "?"), message.body.get("reason", ""))

    def _on_strategy(self, message):
        strategy = message.body.get("strategy", {})
        max_tasks = strategy.get("max_concurrent_tasks", 3)
        self.operations["max_concurrent"] = max_tasks
        self.logger.info("Strategy updated: max %d concurrent tasks", max_tasks)

    async def think(self, context: dict) -> dict:
        prompt = (
            "As COO of AGENT007, analyze operations:\n\n"
            "Current ops state: %s\n"
            "Queue depth: %d\n"
            "Tasks completed: %d\n"
            "Tasks failed: %d\n\n"
            "Decide: are we running smoothly? Any bottlenecks? "
            "Should we increase/decrease concurrent task count? "
            "Respond JSON with: status (green/yellow/red), "
            "recommended_concurrent_tasks (int), bottlenecks (list), "
            "actions (str)." % (
                str(self.operations),
                self.operations["queue_depth"],
                self.operations["tasks_completed"],
                self.operations["tasks_failed"],
            )
        )
        result = self._llm_decide(prompt)
        self.save_decision("ops_analysis", context, result)
        return result

    def get_ops_summary(self) -> dict:
        return {**self.operations, "goals": self.goals[:3]}
