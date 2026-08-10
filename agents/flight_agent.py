"""Flight Agent - handles flight-related queries."""

import logging
from typing import Dict, Any
from .base_agent import BaseAgent, AgentCard, Skill
from mcp_servers.flight_mcp import flight_mcp

logger = logging.getLogger(__name__)


class FlightAgent(BaseAgent):
    """Agent for flight queries using mock data."""

    def __init__(self):
        """Initialize flight agent."""
        super().__init__(
            name="Flight Agent",
            description="提供航班查询和机票预订服务，支持搜索航班和获取航班详情",
            version="1.0.0",
        )

        # Register skills
        self.register_skill(
            Skill(
                name="search_flights",
                description="搜索可用航班",
                tags=["flight", "booking"],
            )
        )
        self.register_skill(
            Skill(
                name="get_flight_detail",
                description="获取航班详细信息",
                tags=["flight", "detail"],
            )
        )

    def get_agent_card(self, base_url: str) -> AgentCard:
        """Get agent card for A2A protocol."""
        return AgentCard(
            name=self.name,
            description=self.description,
            version=self.version,
            url=base_url,
            skills=self.skills,
            capabilities={
                "streaming": False,
                "pushNotifications": False,
            },
        )

    async def handle_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming task request."""
        skill_name = task.get("skill")
        parameters = task.get("parameters", {})

        if not skill_name:
            return {"error": True, "message": "No skill specified"}

        return await self.execute_skill(skill_name, parameters)

    async def skill_search_flights(
        self,
        departure: str,
        arrival: str,
        date: str,
        passengers: int = 1,
    ) -> Dict[str, Any]:
        """
        Search for available flights.

        Args:
            departure: Departure city
            arrival: Arrival city
            date: Travel date
            passengers: Number of passengers

        Returns:
            Flight search results
        """
        return await flight_mcp.search_flights(departure, arrival, date, passengers)

    async def skill_get_flight_detail(
        self,
        flight_no: str,
        date: str,
    ) -> Dict[str, Any]:
        """
        Get flight detail.

        Args:
            flight_no: Flight number
            date: Flight date

        Returns:
            Flight detail
        """
        return await flight_mcp.get_flight_detail(flight_no, date)


# Global instance
flight_agent = FlightAgent()
