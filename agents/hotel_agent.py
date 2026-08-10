"""Hotel Agent - handles hotel-related queries."""

import logging
from typing import Dict, Any
from .base_agent import BaseAgent, AgentCard, Skill
from mcp_servers.hotel_mcp import hotel_mcp

logger = logging.getLogger(__name__)


class HotelAgent(BaseAgent):
    """Agent for hotel queries using mock data."""

    def __init__(self):
        """Initialize hotel agent."""
        super().__init__(
            name="Hotel Agent",
            description="提供酒店查询和预订服务，支持搜索酒店和获取酒店详情",
            version="1.0.0",
        )

        # Register skills
        self.register_skill(
            Skill(
                name="search_hotels",
                description="搜索可用酒店",
                tags=["hotel", "booking"],
            )
        )
        self.register_skill(
            Skill(
                name="get_hotel_detail",
                description="获取酒店详细信息",
                tags=["hotel", "detail"],
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

    async def skill_search_hotels(
        self,
        location: str,
        check_in: str,
        check_out: str,
        guests: int = 2,
        price_range: str = None,
    ) -> Dict[str, Any]:
        """
        Search for available hotels.

        Args:
            location: City name
            check_in: Check-in date
            check_out: Check-out date
            guests: Number of guests
            price_range: Price range

        Returns:
            Hotel search results
        """
        return await hotel_mcp.search_hotels(location, check_in, check_out, guests, price_range)

    async def skill_get_hotel_detail(
        self,
        hotel_name: str,
        date: str,
    ) -> Dict[str, Any]:
        """
        Get hotel detail.

        Args:
            hotel_name: Hotel name
            date: Check-in date

        Returns:
            Hotel detail
        """
        return await hotel_mcp.get_hotel_detail(hotel_name, date)


# Global instance
hotel_agent = HotelAgent()
