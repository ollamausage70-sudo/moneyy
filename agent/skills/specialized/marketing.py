from agent.brain import LLMBrain
from agent.skills.base import Task
from .base import SpecializedSkill


class MarketingSkill(SpecializedSkill):
    def __init__(self, brain: LLMBrain):
        super().__init__("marketing", brain)
        self.keywords = [
            "marketing", "seo", "social media", "ad copy", "advertisement",
            "facebook ad", "google ad", "linkedin", "twitter", "instagram",
            "tiktok", "youtube", "content marketing", "email marketing",
            "newsletter", "campaign", "conversion", "cta", "landing page",
            "brand", "branding", "copywriting", "sales copy", "pitch",
            "promotion", "lead magnet", "funnel", "growth", "acquisition",
            "keyword research", "backlink", "organic", "ppc", "cpc",
            "audience", "targeting", "segmentation", "a/b testing",
            "analytics", "metrics", "kpi", "roi", "engagement",
        ]

    def confidence(self, task: Task) -> float:
        text = (task.title + " " + task.description).lower()
        matches = sum(1 for kw in self.keywords if kw in text)
        return min(matches / 4, 1.0)

    def evaluate(self, task: Task, bid: float) -> tuple[bool, str, float]:
        decision = self.brain.decide(
            f"Evaluate this MARKETING task:\n\nTitle: {task.title}\n"
            f"Description: {task.description}\nReward: ${task.reward}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"I am a marketing expert: SEO, social media, ads, email, "
            f"copywriting, and analytics.\n"
            f"Can I do this with AI? Respond JSON: "
            f'{{"can_do": bool, "bid_amount": float, "reason": "..."}}'
        )
        return decision.get("can_do", False), decision.get("reason", ""), float(decision.get("bid_amount", bid))

    def generate_proposal(self, task: Task) -> str:
        return self.brain.think(
            f"Write a winning proposal for this marketing task.\n\n"
            f"Title: {task.title}\nDescription: {task.description}\n"
            f"Reward: ${task.reward}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"Rules: ONE sentence showing marketing strategy understanding. "
            f"ONE sentence on deliverables and timeline. "
            f"Close with a handshake. Under 80 words."
        )

    def complete(self, task: Task) -> str:
        self.tasks_done += 1
        return self.brain.think(
            f"Complete this marketing task with professional quality:\n\n"
            f"Task: {task.title}\nDescription: {task.description}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"Deliver polished, results-driven marketing content."
        )
