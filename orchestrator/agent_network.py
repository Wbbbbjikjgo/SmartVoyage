"""Agent network management."""

import logging
from typing import Dict, Any, List, Optional
from agents import (
    WeatherAgent,
    FlightAgent,
    HotelAgent,
    ItineraryAgent,
    BaseAgent,
)
from configs.settings import settings

logger = logging.getLogger(__name__)


class AgentNetwork:
    """Manages the network of A2A agents."""

    def __init__(self):
        """Initialize agent network."""
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_urls: Dict[str, str] = {}
        self._register_default_agents()

    def _register_default_agents(self):
        """Register default agents."""
        # Weather Agent
        self.register_agent(
            "weather",
            WeatherAgent(),
            f"http://localhost:{settings.weather_agent_port}",
        )

        # Flight Agent
        self.register_agent(
            "flight",
            FlightAgent(),
            f"http://localhost:{settings.flight_agent_port}",
        )

        # Hotel Agent
        self.register_agent(
            "hotel",
            HotelAgent(),
            f"http://localhost:{settings.hotel_agent_port}",
        )

        # Itinerary Agent
        self.register_agent(
            "itinerary",
            ItineraryAgent(),
            f"http://localhost:{settings.itinerary_agent_port}",
        )

    def register_agent(
        self,
        name: str,
        agent: BaseAgent,
        url: str,
    ):
        """
        Register an agent in the network.

        Args:
            name: Agent name/key
            agent: Agent instance
            url: Agent URL
        """
        self.agents[name] = agent
        self.agent_urls[name] = url
        logger.info(f"Registered agent: {name} at {url}")

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """
        Get agent by name.

        Args:
            name: Agent name

        Returns:
            Agent instance or None
        """
        return self.agents.get(name)

    def get_agent_url(self, name: str) -> Optional[str]:
        """
        Get agent URL by name.

        Args:
            name: Agent name

        Returns:
            Agent URL or None
        """
        return self.agent_urls.get(name)

    def list_agents(self) -> List[Dict[str, Any]]:
        """
        List all registered agents.

        Returns:
            List of agent info dicts
        """
        result = []
        for name, agent in self.agents.items():
            result.append({
                "name": name,
                "agent_name": agent.name,
                "description": agent.description,
                "version": agent.version,
                "url": self.agent_urls.get(name),
                "skills": [s.name for s in agent.skills],
            })
        return result

    def get_agent_card(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get agent card for a specific agent.

        Args:
            name: Agent name

        Returns:
            Agent card dict or None
        """
        agent = self.agents.get(name)
        url = self.agent_urls.get(name)
        if not agent or not url:
            return None

        card = agent.get_agent_card(url)
        return card.to_dict()

    async def invoke_agent(
        self,
        agent_name: str,
        skill: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Invoke an agent's skill.

        Args:
            agent_name: Agent name
            skill: Skill name
            parameters: Skill parameters

        Returns:
            Skill execution result
        """
        agent = self.agents.get(agent_name)
        if not agent:
            return {
                "error": True,
                "message": f"Agent not found: {agent_name}",
            }

        task = {
            "skill": skill,
            "parameters": parameters,
        }

        return await agent.handle_task(task)


# Global instance
agent_network = AgentNetwork()
