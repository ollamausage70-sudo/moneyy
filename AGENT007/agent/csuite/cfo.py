import logging
from typing import Optional

from agent.brain import LLMBrain
from agent.database import DatabaseManager
from .base import CLevelAgent, Authority
from .message_bus import MessageBus

logger = logging.getLogger("csuite.cfo")


class CFOAgent(CLevelAgent):
    def __init__(self, brain: LLMBrain, bus: MessageBus, db: DatabaseManager):
        super().__init__("CFO", "Chief Financial Officer", Authority.FINANCE, brain, bus, db)
        self.budget = {
            "max_bid_per_task": 50.0,
            "daily_llm_budget": 2.0,
            "total_earned": 0.0,
            "total_costs": 0.0,
        }
        self.transactions: list[dict] = []
        self.set_goal("Track every dollar earned and spent", 10)
        self.set_goal("Maintain positive P&L", 9)
        self.set_goal("Optimize bid pricing for max ROI", 7)

        self.bus.subscribe("request:budget_approval", self._on_budget_request)
        self.bus.subscribe("payment:confirmed", self._on_payment_confirmed)
        self.bus.subscribe("broadcast:strategy", self._on_strategy)

    def _on_budget_request(self, message):
        body = message.body
        task_id = body.get("task_id", "?")
        bid_amount = body.get("bid_amount", 0)
        task_reward = body.get("task_reward", 0)

        roi = (task_reward - bid_amount) / bid_amount if bid_amount > 0 else 0

        if bid_amount > self.budget["max_bid_per_task"]:
            self.logger.info("DENIED %s: bid $%s exceeds max $%s", task_id, bid_amount, self.budget["max_bid_per_task"])
            self.bus.reply(message, {"approved": False, "reason": "Exceeds max bid per task"})
            return

        if roi < 0.5 and bid_amount > 10:
            self.logger.info("DENIED %s: ROI %.0f%% too low", task_id, roi * 100)
            self.bus.reply(message, {"approved": False, "reason": "Insufficient ROI"})
            return

        self.logger.info("APPROVED %s: bid $%s, reward $%s (ROI %.0f%%)", task_id, bid_amount, task_reward, roi * 100)
        self.bus.reply(message, {"approved": True, "reason": "ROI acceptable"})

    def _on_payment_confirmed(self, message):
        amount = message.body.get("amount", 0)
        source = message.body.get("source", "unknown")
        self.budget["total_earned"] += amount
        self.transactions.append({"type": "earning", "amount": amount, "source": source})
        self.logger.info("Payment confirmed: +$%s from %s", amount, source)

    def _on_strategy(self, message):
        body = message.body.get("strategy", {})
        aggression = body.get("aggression_level", "moderate")
        if aggression == "aggressive":
            self.budget["max_bid_per_task"] = 75.0
        elif aggression == "conservative":
            self.budget["max_bid_per_task"] = 25.0
        else:
            self.budget["max_bid_per_task"] = 50.0
        self.logger.info("Budget adjusted for %s strategy: max bid $%s", aggression, self.budget["max_bid_per_task"])

    async def think(self, context: dict) -> dict:
        prompt = (
            "As CFO of AGENT007, analyze the financial situation:\n\n"
            "Budget: %s\n"
            "Recent transactions: %s\n"
            "Total earned: $%s\n"
            "Total costs: $%s\n\n"
            "Provide financial recommendations: should we increase or decrease "
            "bid limits? Which marketplaces are most profitable? Any cost concerns? "
            "Respond JSON with: recommended_max_bid, profitability_score (0-100), "
            "cost_concerns (list), recommendations (str)." % (
                str(self.budget),
                str(self.transactions[-5:]),
                self.budget["total_earned"],
                self.budget["total_costs"],
            )
        )
        result = self._llm_decide(prompt)

        if result.get("recommended_max_bid"):
            self.budget["max_bid_per_task"] = float(result["recommended_max_bid"])

        self.save_decision("financial_analysis", context, result)
        return result

    def get_financial_summary(self) -> dict:
        return {**self.budget, "transactions_count": len(self.transactions)}
