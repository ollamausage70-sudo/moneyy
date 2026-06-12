import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Task:
    id: str
    title: str
    description: str
    reward: float
    reward_currency: str
    source: str
    status: str = "open"
    url: Optional[str] = None
    requirements: Optional[str] = None
    deadline: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class EarningRecord:
    task_id: str
    source: str
    amount: float
    currency: str
    timestamp: datetime
    description: str
    tx_hash: Optional[str] = None


class BaseSkill(ABC):
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"agent.skill.{name}")
        self.earnings: list[EarningRecord] = []
        self.tasks_seen: set = set()

    @abstractmethod
    async def find_opportunities(self) -> list[Task]:
        pass

    @abstractmethod
    async def execute(self, task: Task) -> Optional[str]:
        pass

    def get_earnings_summary(self) -> dict:
        total = sum(e.amount for e in self.earnings)
        return {
            "skill": self.name,
            "total_earned": total,
            "tasks_done": len(self.earnings),
            "tasks_seen": len(self.tasks_seen),
            "currency": "USDC",
        }
