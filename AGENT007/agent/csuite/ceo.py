import logging
from typing import Optional

from agent.brain import LLMBrain
from agent.database import DatabaseManager
from .base import CLevelAgent, Authority
from .message_bus import MessageBus

logger = logging.getLogger("csuite.ceo")


class CEOAgent(CLevelAgent):
    def __init__(self, brain: LLMBrain, bus: MessageBus, db: DatabaseManager):
        super().__init__("CEO", "Chief Executive Officer", Authority.FOUNDER, brain, bus, db)
        self.current_strategy = {
            "focus_marketplaces": [],
            "focus_task_types": [],
            "max_concurrent_tasks": 3,
            "aggression_level": "moderate",
            "priority_platforms": [],
        }
        self.set_goal("Achieve first $100 USDC in earnings", 10)
        self.set_goal("Optimize marketplace selection for best ROI", 8)
        self.set_goal("Build sustainable autonomous earning pipeline", 7)

        self.bus.subscribe("report:weekly", self._on_weekly_report)
        self.bus.subscribe("report:financial", self._on_financial_report)
        self.bus.subscribe("report:operations", self._on_ops_report)

    def _on_weekly_report(self, message):
        self.logger.info("Weekly report received from %s", message.sender)

    def _on_financial_report(self, message):
        body = message.body
        self.logger.info("Financial report: $%s earned, $%s costs",
                        body.get("total_earned", 0), body.get("total_costs", 0))

    def _on_ops_report(self, message):
        body = message.body
        self.logger.info("Ops report: %d tasks completed, %d failed",
                        body.get("completed", 0), body.get("failed", 0))

    async def think(self, context: dict) -> dict:
        reports = context.get("reports", {})
        prompt = (
            "As CEO of AGENT007, analyze these reports and set strategy:\n\n"
            "Financial: %s\n"
            "Operations: %s\n"
            "Learning: %s\n"
            "Current strategy: %s\n\n"
            "Decide: which marketplaces to prioritize, which task types to pursue, "
            "what aggression level to use, and any strategic shifts. "
            "Respond JSON with keys: priority_marketplaces (list), "
            "focus_task_types (list), aggression (conservative/moderate/aggressive), "
            "strategic_notes (str)." % (
                str(context.get("financial", {})),
                str(context.get("operations", {})),
                str(context.get("learning", {})),
                str(self.current_strategy),
            )
        )
        result = self._llm_decide(prompt)

        if result.get("priority_marketplaces"):
            self.current_strategy["focus_marketplaces"] = result["priority_marketplaces"]
        if result.get("focus_task_types"):
            self.current_strategy["focus_task_types"] = result["focus_task_types"]

        self.broadcast("broadcast:strategy", {
            "from": "CEO",
            "strategy": self.current_strategy,
            "decision": result,
        })
        self.save_decision("strategy_set", context, result)
        return result

    def get_strategy(self) -> dict:
        return {**self.current_strategy, "goals": self.goals[:3]}
