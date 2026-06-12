from typing import Optional

from agent.brain import LLMBrain
from agent.skills.base import Task
from .base import SpecializedSkill


class ResearchAnalystSkill(SpecializedSkill):
    def __init__(self, brain: LLMBrain):
        super().__init__("research_analyst", brain)
        self.keywords = [
            "research", "analysis", "analyze", "report", "data",
            "market research", "competitor", "industry", "trend",
            "survey", "statistics", "spreadsheet", "excel", "csv",
            "data entry", "data cleaning", "data processing",
            "data collection", "web scraping", "extract",
            "summarize", "summary", "comparison", "evaluate",
            "investigate", "study", "findings", "insights",
            "dashboard", "metrics", "kpi", "forecast", "predict",
            "classification", "categorize", "organize", "list",
            "leads", "lead generation", "enrichment", "verify",
            "fact check", "validate", "audit", "review",
        ]

    def confidence(self, task: Task) -> float:
        text = (task.title + " " + task.description).lower()
        matches = sum(1 for kw in self.keywords if kw in text)
        score = min(matches / 4, 1.0)
        return score

    def evaluate(self, task: Task, bid: float) -> tuple[bool, str, float]:
        prompt = (
            f"Evaluate this RESEARCH/DATA task for AGENT007:\n\n"
            f"Title: {task.title}\n"
            f"Description: {task.description}\n"
            f"Reward: ${task.reward}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"I am an expert research analyst. I can analyze data, "
            f"write reports, do deep research, create spreadsheets, "
            f"collect and organize information.\n\n"
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
            f"Write a winning proposal for this research task.\n\n"
            f"Title: {task.title}\n"
            f"Description: {task.description}\n"
            f"Reward: ${task.reward}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"Rules: ONE sentence showing research approach. "
            f"ONE sentence on deliverables and timeline. "
            f"Close with a handshake. Under 80 words."
        )
        return self.brain.think(prompt)

    def complete(self, task: Task) -> str:
        prompt = (
            f"Complete this research task with thorough, well-organized findings:\n\n"
            f"Task: {task.title}\n"
            f"Description: {task.description}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"Deliver a comprehensive, well-structured report. "
            f"Use data and evidence. Format for clarity."
        )
        self.tasks_done += 1
        return self.brain.think(prompt)
