import json
import logging
from datetime import datetime
from typing import Optional

from agent.brain import LLMBrain
from agent.database import DatabaseManager
from .base import CLevelAgent, Authority
from .message_bus import MessageBus

logger = logging.getLogger("csuite.learning")


class LearningAgent(CLevelAgent):
    def __init__(self, brain: LLMBrain, bus: MessageBus, db: DatabaseManager):
        super().__init__("Learning", "Learning & Analytics", Authority.STRATEGY, brain, bus, db)
        self.insights: list[dict] = []
        self.set_goal("Identify top 3 most profitable task types", 9)
        self.set_goal("Reduce cost per task by 20% through learning", 8)

        self.bus.subscribe("request:insights", self._on_request_insights)
        self.bus.subscribe("learning:data_point", self._on_data_point)

    def _on_request_insights(self, message):
        self.bus.reply(message, {"insights": self.insights[-5:]})

    def _on_data_point(self, message):
        body = message.body
        category = body.get("category", "generic")
        self.db.save_learning_data(category, body.get("data", {}))
        self.logger.debug("Learning data point: %s", category)

    def analyze_trends(self) -> dict:
        earnings = self.db.get_earnings(100)
        decisions = self.db.get_csuite_decisions(limit=50)

        by_source = {}
        for e in earnings:
            src = e.get("source", "unknown")
            if src not in by_source:
                by_source[src] = {"count": 0, "total": 0.0}
            by_source[src]["count"] += 1
            by_source[src]["total"] += float(e.get("amount", 0))

        insight = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_earnings": len(earnings),
            "earnings_by_source": by_source,
            "total_csuite_decisions": len(decisions),
            "best_source": max(by_source, key=lambda s: by_source[s]["total"]) if by_source else None,
        }
        self.insights.append(insight)
        self.insights = self.insights[-20:]
        return insight

    async def think(self, context: dict) -> dict:
        analysis = self.analyze_trends()
        prompt = (
            "As Learning & Analytics for AGENT007, analyze trends:\n\n"
            "Latest insights: %s\n"
            "Best performing source: %s\n"
            "Total earnings tracked: %d\n\n"
            "What patterns do you see? Which task types or platforms "
            "are most profitable? Any recommendations for CEO? "
            "Respond JSON with: best_opportunity (str), "
            "recommended_focus (str), predicted_trends (list), "
            "actionable_insights (list)." % (
                str(analysis),
                analysis.get("best_source"),
                analysis.get("total_earnings"),
            )
        )
        result = self._llm_decide(prompt)
        self.save_decision("trend_analysis", context, result)
        return result

    def get_learning_summary(self) -> dict:
        return {
            "insights_count": len(self.insights),
            "latest_insight": self.insights[-1] if self.insights else None,
            "recent_insights": self.insights[-3:],
        }
