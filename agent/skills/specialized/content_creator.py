from typing import Optional

from agent.brain import LLMBrain
from agent.skills.base import Task
from .base import SpecializedSkill


class ContentCreatorSkill(SpecializedSkill):
    def __init__(self, brain: LLMBrain):
        super().__init__("content_creator", brain)
        self.keywords = [
            "write", "content", "blog", "article", "copy", "marketing",
            "translate", "translation", "language", "grammar", "edit",
            "proofread", "social media", "post", "newsletter", "email",
            "seo", "keyword", "description", "product description",
            "press release", "script", "video script", "caption",
            "headline", "tagline", "slogan", "landing page",
            "website copy", "ad copy", "creative writing", "story",
            "essay", "report writing", "document", "documentation",
        ]

    def confidence(self, task: Task) -> float:
        text = (task.title + " " + task.description).lower()
        matches = sum(1 for kw in self.keywords if kw in text)
        score = min(matches / 5, 1.0)
        return score

    def evaluate(self, task: Task, bid: float) -> tuple[bool, str, float]:
        prompt = (
            f"Evaluate this CONTENT CREATION task for AGENT007:\n\n"
            f"Title: {task.title}\n"
            f"Description: {task.description}\n"
            f"Reward: ${task.reward}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"I am an expert content creator. I can write, translate, edit, "
            f"and optimize content in any language with high quality.\n\n"
            f"Can I complete this entirely with AI? "
            f"Respond JSON: {{\"can_do\": bool, \"bid_amount\": float, "
            f"\"reason\": \"...\", \"effort\": \"low/medium/high\"}}"
        )
        decision = self.brain.decide(prompt)
        can_do = decision.get("can_do", False)
        final_bid = float(decision.get("bid_amount", bid))
        reason = decision.get("reason", "")
        return can_do, reason, final_bid

    def generate_proposal(self, task: Task) -> str:
        prompt = (
            f"Write a winning proposal for this content task.\n\n"
            f"Title: {task.title}\n"
            f"Description: {task.description}\n"
            f"Reward: ${task.reward}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"Rules: ONE sentence showing you understand the content need. "
            f"ONE sentence on what you'll deliver and when. "
            f"Close with a handshake. Under 80 words. Be specific."
        )
        return self.brain.think(prompt)

    def complete(self, task: Task) -> str:
        prompt = (
            f"Complete this content creation task with professional quality:\n\n"
            f"Task: {task.title}\n"
            f"Description: {task.description}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"Deliver high-quality, publication-ready content. "
            f"Be thorough and well-formatted."
        )
        self.tasks_done += 1
        return self.brain.think(prompt)
