import logging
from abc import ABC, abstractmethod
from typing import Optional

from agent.brain import LLMBrain
from agent.skills.base import Task


class SpecializedSkill(ABC):
    def __init__(self, name: str, brain: LLMBrain):
        self.name = name
        self.brain = brain
        self.logger = logging.getLogger(f"agent.skill.{name}")
        self.tasks_done = 0

    @abstractmethod
    def confidence(self, task: Task) -> float:
        pass

    @abstractmethod
    def evaluate(self, task: Task, bid: float) -> tuple[bool, str, float]:
        pass

    @abstractmethod
    def generate_proposal(self, task: Task) -> str:
        pass

    @abstractmethod
    def complete(self, task: Task) -> str:
        pass

    def get_info(self) -> dict:
        return {"name": self.name, "tasks_done": self.tasks_done}
