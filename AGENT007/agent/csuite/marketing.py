import logging
from typing import Optional

from agent.brain import LLMBrain
from agent.database import DatabaseManager
from .base import CLevelAgent, Authority
from .message_bus import MessageBus

logger = logging.getLogger("csuite.marketing")


class MarketingAgent(CLevelAgent):
    def __init__(self, brain: LLMBrain, bus: MessageBus, db: DatabaseManager):
        super().__init__("Marketing", "Marketing Manager", Authority.SUPPORT, brain, bus, db)
        self.reputation_scores: dict[str, float] = {}
        self.proposals_written = 0
        self.bid_win_rate = 0.0
        self.set_goal("Improve bid win rate to >30%", 8)
        self.set_goal("Build strong agent reputation on all marketplaces", 7)

        self.bus.subscribe("proposal:written", self._on_proposal_written)
        self.bus.subscribe("bid:result", self._on_bid_result)
        self.bus.subscribe("broadcast:strategy", self._on_strategy)

    def _on_proposal_written(self, message):
        self.proposals_written += 1

    def _on_bid_result(self, message):
        won = message.body.get("won", False)
        platform = message.body.get("platform", "unknown")
        if platform not in self.reputation_scores:
            self.reputation_scores[platform] = 50.0
        if won:
            self.reputation_scores[platform] = min(100, self.reputation_scores[platform] + 2)
        else:
            self.reputation_scores[platform] = max(0, self.reputation_scores[platform] - 1)

        total = sum(1 for _ in [True])
        self.bid_win_rate = (
            self.reputation_scores.get(platform, 50) / 100
        )

    def _on_strategy(self, message):
        pass

    def generate_proposal_template(self, task_title: str, task_description: str, platform: str) -> str:
        prompt = (
            "Write a winning proposal template for this task type.\n\n"
            "Platform: %s\n"
            "Task title: %s\n"
            "Description: %s\n\n"
            "Write a professional, concise proposal (under 100 words) "
            "that: shows understanding of the task, demonstrates relevant "
            "skills, offers a clear deliverable, and includes a call to action. "
            "Respond with only the proposal text." % (
                platform, task_title, task_description[:500],
            )
        )
        result = self._llm_decide(prompt)
        return result.get("decision", prompt)

    async def think(self, context: dict) -> dict:
        prompt = (
            "As Marketing Manager for AGENT007:\n\n"
            "Reputation scores: %s\n"
            "Proposals written: %d\n"
            "Bid win rate: %.0f%%\n\n"
            "How can we improve our proposals and reputation? "
            "Any platform-specific strategies? "
            "Respond JSON with: focus_platform (str), "
            "improvement_tips (list), proposal_angle (str)." % (
                str(self.reputation_scores),
                self.proposals_written,
                self.bid_win_rate * 100,
            )
        )
        result = self._llm_decide(prompt)
        self.save_decision("marketing_analysis", context, result)
        return result

    def get_marketing_summary(self) -> dict:
        return {
            "reputation_scores": self.reputation_scores,
            "proposals_written": self.proposals_written,
            "bid_win_rate": round(self.bid_win_rate * 100, 1),
        }
