import logging
from typing import Optional

from .base import CLevelAgent, Authority
from .message_bus import MessageBus

logger = logging.getLogger("csuite.registry")


class CSuiteRegistry:
    def __init__(self, bus: MessageBus):
        self.bus = bus
        self.agents: dict[str, CLevelAgent] = {}

    def register(self, agent: CLevelAgent):
        self.agents[agent.name] = agent
        logger.info("Registered C-Suite agent: %s (%s)", agent.name, agent.title)
        self.bus.broadcast("registry", "agent_registered", {
            "agent": agent.name,
            "title": agent.title,
            "authority": agent.authority.name,
        })

    def get(self, name: str) -> Optional[CLevelAgent]:
        return self.agents.get(name)

    def get_by_authority(self, authority: Authority) -> list[CLevelAgent]:
        return [a for a in self.agents.values() if a.authority == authority]

    def get_chain_of_command(self, agent_name: str) -> list[str]:
        agent = self.agents.get(agent_name)
        if not agent:
            return []
        higher = [a.name for a in self.agents.values() if a.authority > agent.authority]
        higher.sort(key=lambda n: self.agents[n].authority, reverse=True)
        return higher

    def get_status(self) -> dict:
        return {
            "agents": {name: agent.get_status() for name, agent in self.agents.items()},
            "org_chart": {
                "executive": [a.name for a in self.get_by_authority(Authority.EXECUTIVE)],
                "finance": [a.name for a in self.get_by_authority(Authority.FINANCE)],
                "strategy": [a.name for a in self.get_by_authority(Authority.STRATEGY)],
                "operations": [a.name for a in self.get_by_authority(Authority.OPERATIONS)],
                "support": [a.name for a in self.get_by_authority(Authority.SUPPORT)],
            },
        }
