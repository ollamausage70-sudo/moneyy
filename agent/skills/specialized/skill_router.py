import logging
from typing import Optional

from agent.brain import LLMBrain
from agent.skills.base import Task
from .base import SpecializedSkill

logger = logging.getLogger("agent.skill_router")


class SkillRouter:
    def __init__(self, brain: LLMBrain):
        self.brain = brain
        self.skills: list[SpecializedSkill] = []

    def register(self, skill: SpecializedSkill):
        self.skills.append(skill)
        logger.info(f"Registered specialized skill: {skill.name}")

    def pick(self, task: Task) -> Optional[SpecializedSkill]:
        scored = [(skill.confidence(task), skill) for skill in self.skills]
        scored.sort(key=lambda x: -x[0])
        best = scored[0] if scored else (0, None)
        if best[0] >= 0.3:
            logger.info(f"Router picked {best[1].name} for '{task.title}' (confidence: {best[0]:.0%})")
            return best[1]
        logger.info(f"Router: no skill confident enough for '{task.title}', using generic")
        return None

    def evaluate(self, task: Task, default_bid: float) -> tuple[bool, str, float, Optional[str]]:
        skill = self.pick(task)
        if skill:
            return True, f"Auto-matched to {skill.name}", default_bid, skill.name
        text = (task.title + " " + task.description).lower()
        generic_keywords = ["write", "code", "research", "data", "translate",
                            "analysis", "report", "content", "review", "fix",
                            "summarize", "create", "edit", "help", "task"]
        if any(kw in text for kw in generic_keywords):
            return True, "Generic task matched keywords", default_bid, None
        return False, "No matching skill or keywords", 0, None

    def generate_proposal(self, task: Task) -> str:
        skill = self.pick(task)
        if skill:
            return skill.generate_proposal(task)
        prompt = (
            f"Write a winning proposal for this task.\n\n"
            f"Title: {task.title}\n"
            f"Description: {task.description}\n"
            f"Reward: ${task.reward}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"Rules: ONE sentence showing you understand the need. "
            f"ONE sentence on deliverable plus timeline. "
            f"Close with a handshake offer. Under 80 words. "
            f"Be specific, not generic."
        )
        return self.brain.think(prompt)

    def complete(self, task: Task) -> tuple[str, Optional[str]]:
        skill = self.pick(task)
        if skill:
            return skill.complete(task), skill.name
        prompt = (
            f"Complete this task with high quality:\n\n"
            f"Task: {task.title}\n"
            f"Description: {task.description}\n"
            f"Requirements: {task.requirements or 'None'}"
        )
        return self.brain.think(prompt), None

    def get_stats(self) -> dict:
        return {s.name: s.get_info() for s in self.skills}
