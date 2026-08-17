"""Hotel Agent - handles hotel-related queries."""

import logging
from typing import Any, Dict, Optional
from .base_agent import BaseAgent, AgentCard, Skill
from mcp_servers.hotel_mcp import hotel_mcp

logger = logging.getLogger(__name__)


class HotelAgent(BaseAgent):
    """Agent for hotel queries backed by the AMap POI search."""

    def __init__(self):
        """Initialize hotel agent."""
        super().__init__(
            name="Hotel Agent",
            description="提供酒店搜索与酒店详情查询（数据来源：高德开放平台）",
            version="2.0.0",
        )

        self.register_skill(
            Skill(
                name="search_hotels",
                description="搜索可用酒店",
                tags=["hotel", "search"],
            )
        )
        self.register_skill(
            Skill(
                name="get_hotel_detail",
                description="获取酒店详细信息",
                tags=["hotel", "detail"],
            )
        )
        self.register_skill(
            Skill(
                name="search_attractions",
                description="搜索指定城市的景点",
                tags=["attraction", "search"],
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
        check_in: str = "",
        check_out: str = "",
        guests: int = 2,
    ) -> Dict[str, Any]:
        """搜索可用酒店。"""
        return await hotel_mcp.search_hotels(location, check_in, check_out, guests)

    async def skill_get_hotel_detail(
        self, hotel_name: str, city: str = "", date: str = ""
    ) -> Dict[str, Any]:
        """获取酒店详细信息。"""
        return await hotel_mcp.get_hotel_detail(hotel_name, city, date)

    async def skill_search_attractions(
        self, location: str, limit: int = 10
    ) -> Dict[str, Any]:
        """搜索指定城市的景点。"""
        return await hotel_mcp.search_attractions(location, limit)


# Global instance
hotel_agent = HotelAgent()
