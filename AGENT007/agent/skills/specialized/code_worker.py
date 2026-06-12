from typing import Optional

from agent.brain import LLMBrain
from agent.skills.base import Task
from .base import SpecializedSkill


class CodeWorkerSkill(SpecializedSkill):
    def __init__(self, brain: LLMBrain):
        super().__init__("code_worker", brain)
        self.keywords = [
            "code", "programming", "python", "javascript", "typescript",
            "react", "node", "api", "backend", "frontend", "web",
            "script", "function", "class", "debug", "bug", "error",
            "fix", "implement", "refactor", "optimize", "algorithm",
            "data structure", "git", "github", "sql", "database",
            "html", "css", "json", "rest", "graphql", "docker",
            "test", "unit test", "deploy", "ci/cd", "automation",
            "scraping", "crawl", "bot", "integration", "migration",
            "readme", "docs", "technical", "api endpoint", "server",
            "async", "await", "promise", "callback", "variable",
        ]

    def confidence(self, task: Task) -> float:
        text = (task.title + " " + task.description).lower()
        matches = sum(1 for kw in self.keywords if kw in text)
        score = min(matches / 4, 1.0)
        return score

    def evaluate(self, task: Task, bid: float) -> tuple[bool, str, float]:
        prompt = (
            f"Evaluate this CODE/DEVELOPMENT task for AGENT007:\n\n"
            f"Title: {task.title}\n"
            f"Description: {task.description}\n"
            f"Reward: ${task.reward}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"I am an expert developer. I can write, debug, and optimize "
            f"code, build APIs, fix bugs, write tests, and automate tasks.\n\n"
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
            f"Write a winning proposal for this development task.\n\n"
            f"Title: {task.title}\n"
            f"Description: {task.description}\n"
            f"Reward: ${task.reward}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"Rules: ONE sentence showing technical understanding. "
            f"ONE sentence on solution and delivery timeline. "
            f"Close with a handshake. Under 80 words. Be specific."
        )
        return self.brain.think(prompt)

    def complete(self, task: Task) -> str:
        prompt = (
            f"Complete this development task with clean, working code:\n\n"
            f"Task: {task.title}\n"
            f"Description: {task.description}\n"
            f"Requirements: {task.requirements or 'None'}\n\n"
            f"Write well-structured, documented code. Include usage examples."
        )
        self.tasks_done += 1
        return self.brain.think(prompt)
