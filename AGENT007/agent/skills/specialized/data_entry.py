from agent.brain import LLMBrain
from agent.skills.base import Task
from .base import SpecializedSkill


class DataEntrySkill(SpecializedSkill):
    def __init__(self, brain: LLMBrain):
        super().__init__("data_entry", brain)
        self.keywords = [
            "data entry", "data input", "form filling", "categorize",
            "categorization", "classification", "label", "tag",
            "transcribe", "transcription", "audio", "video to text",
            "spreadsheet", "excel", "csv", "google sheets",
            "organize", "organize data", "clean data", "data cleaning",
            "list", "directory", "inventory", "catalog",
            "copy paste", "copy-paste", "manual input", "typing",
            "data processing", "batch", "extract", "capture",
            "digitize", "convert", "format", "standardize",
        ]

    def confidence(self, task: Task) -> float:
        text = (task.title + " " + task.description).lower()
        matches = sum(1 for kw in self.keywords if kw in text)
        return min(matches / 3, 1.0)

    def evaluate(self, task: Task, bid: float) -> tuple[bool, str, float]:
        decision = self.brain.decide(
            f"Evaluate this DATA ENTRY task:\n\nTitle: {task.title}\n"
            f"Description: {task.description}\nReward: ${task.reward}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"I can enter data, fill forms, categorize, transcribe, "
            f"and process data with high accuracy.\n"
            f"Can I do this fully with AI? Respond JSON: "
            f'{{"can_do": bool, "bid_amount": float, "reason": "..."}}'
        )
        return decision.get("can_do", False), decision.get("reason", ""), float(decision.get("bid_amount", bid))

    def generate_proposal(self, task: Task) -> str:
        return self.brain.think(
            f"Write a winning proposal for this data task.\n\n"
            f"Title: {task.title}\nDescription: {task.description}\n"
            f"Reward: ${task.reward}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"Rules: ONE sentence showing data processing approach. "
            f"ONE sentence on deliverables and timeline. "
            f"Close with a handshake. Under 80 words."
        )

    def complete(self, task: Task) -> str:
        self.tasks_done += 1
        return self.brain.think(
            f"Complete this data task accurately:\n\n"
            f"Task: {task.title}\nDescription: {task.description}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"Deliver clean, organized, accurate data."
        )
