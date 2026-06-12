from agent.brain import LLMBrain
from agent.skills.base import Task
from .base import SpecializedSkill


class TranslationSkill(SpecializedSkill):
    def __init__(self, brain: LLMBrain):
        super().__init__("translation", brain)
        self.keywords = [
            "translate", "translation", "translator", "language",
            "spanish", "french", "german", "chinese", "japanese",
            "arabic", "portuguese", "russian", "korean", "italian",
            "multilingual", "localization", "l10n", "i18n",
            "interpret", "interpretation", "subtitle", "subtitling",
            "dubbing", "voiceover", "transcreation",
            "english to", "from english", "native speaker",
            "bilingual", "language pair", "document translation",
            "website translation", "app localization",
        ]

    def confidence(self, task: Task) -> float:
        text = (task.title + " " + task.description).lower()
        matches = sum(1 for kw in self.keywords if kw in text)
        return min(matches / 2, 1.0)

    def evaluate(self, task: Task, bid: float) -> tuple[bool, str, float]:
        decision = self.brain.decide(
            f"Evaluate this TRANSLATION task:\n\nTitle: {task.title}\n"
            f"Description: {task.description}\nReward: ${task.reward}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"I am a professional translator fluent in all languages. "
            f"I can translate, localize, and adapt content naturally.\n"
            f"Can I do this with AI? Respond JSON: "
            f'{{"can_do": bool, "bid_amount": float, "reason": "..."}}'
        )
        return decision.get("can_do", False), decision.get("reason", ""), float(decision.get("bid_amount", bid))

    def generate_proposal(self, task: Task) -> str:
        return self.brain.think(
            f"Write a winning proposal for this translation task.\n\n"
            f"Title: {task.title}\nDescription: {task.description}\n"
            f"Reward: ${task.reward}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"Rules: ONE sentence showing language expertise. "
            f"ONE sentence on deliverable quality and timeline. "
            f"Close with a handshake. Under 80 words."
        )

    def complete(self, task: Task) -> str:
        self.tasks_done += 1
        return self.brain.think(
            f"Complete this translation task professionally:\n\n"
            f"Task: {task.title}\nDescription: {task.description}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"Deliver natural, accurate translation with cultural adaptation."
        )
