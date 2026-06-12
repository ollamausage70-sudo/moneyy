import logging
from typing import Optional

from agent.brain import LLMBrain
from agent.database import DatabaseManager
from agent.skills.bounty_hunter import BountyHunterSkill
from .base import CLevelAgent, Authority
from .message_bus import MessageBus

logger = logging.getLogger("csuite.bizdev")


class BizDevAgent(CLevelAgent):
    def __init__(self, brain: LLMBrain, bus: MessageBus, db: DatabaseManager, bounty_hunter: BountyHunterSkill = None):
        super().__init__("BizDev", "Business Development", Authority.STRATEGY, brain, bus, db)
        self.bounty_hunter = bounty_hunter
        self.opportunity_pipeline: list[dict] = []
        self.set_goal("Scan all marketplaces for high-value tasks", 10)
        self.set_goal("Build opportunity pipeline with >10 tasks per cycle", 8)
        self.set_goal("Improve opportunity scoring accuracy", 6)

        self.bus.subscribe("request:opportunities", self._on_request_opportunities)
        self.bus.subscribe("broadcast:strategy", self._on_strategy)

    def _on_request_opportunities(self, message):
        self.logger.info("Opportunity request from %s", message.sender)
        tasks = self.opportunity_pipeline[:5]
        self.bus.reply(message, {"opportunities": tasks, "count": len(tasks)})

    def _on_strategy(self, message):
        strategy = message.body.get("strategy", {})
        focus_mps = strategy.get("focus_marketplaces", [])
        if focus_mps:
            self.logger.info("Focusing on marketplaces: %s", focus_mps)

    async def scan_opportunities(self) -> list[dict]:
        if not self.bounty_hunter:
            self.logger.warning("No bounty_hunter skill available")
            return []

        tasks = await self.bounty_hunter.find_opportunities()
        scored = []
        for task in tasks:
            score = self._score_opportunity(task)
            scored.append({
                "task_id": task.id,
                "title": task.title,
                "source": task.source,
                "reward": task.reward,
                "score": score,
                "recommended_bid": self.bounty_hunter._compute_bid(task),
                "skill_match": self.bounty_hunter.router.pick(task).name if self.bounty_hunter.router.pick(task) else "generic",
            })

        scored.sort(key=lambda x: -x["score"])
        self.opportunity_pipeline = scored
        top = scored[:3] if scored else []
        if top:
            self.logger.info("Top opportunities: %s", [t["title"][:30] for t in top])
        return top

    def _score_opportunity(self, task) -> float:
        score = 0.0
        if task.reward > 0:
            score += min(task.reward / 100, 30)
        if task.reward > 20:
            score += 20
        if task.reward < 5:
            score -= 10
        if task.source in ("dealwork", "agenthansa"):
            score += 10
        if task.description and len(task.description) > 100:
            score += 5
        if task.requirements and len(task.requirements) > 0:
            score += 5
        skill = self.bounty_hunter.router.pick(task) if self.bounty_hunter else None
        if skill:
            score += 15
        return score

    async def think(self, context: dict) -> dict:
        pipeline_summary = [
            {"title": t["title"][:30], "source": t["source"], "reward": t["reward"], "score": t["score"]}
            for t in self.opportunity_pipeline[:5]
        ]
        prompt = (
            "As BizDev for AGENT007, analyze the opportunity pipeline:\n\n"
            "Pipeline: %s tasks available\n"
            "Top opportunities: %s\n\n"
            "Which tasks should we pursue? What should we bid? "
            "Any new marketplaces or strategies to explore? "
            "Respond JSON with: recommended_tasks (list of task_ids), "
            "new_marketplaces (list), strategy_notes (str)." % (
                len(self.opportunity_pipeline),
                str(pipeline_summary),
            )
        )
        result = self._llm_decide(prompt)
        self.save_decision("pipeline_analysis", context, result)
        return result

    def get_pipeline_summary(self) -> dict:
        return {
            "pipeline_size": len(self.opportunity_pipeline),
            "top_opportunities": self.opportunity_pipeline[:5],
        }
