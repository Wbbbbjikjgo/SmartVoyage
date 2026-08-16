"""Flight Agent - handles flight-related queries."""

import logging
from typing import Any, Dict, Optional
from .base_agent import BaseAgent, AgentCard, Skill
from mcp_servers.flight_mcp import flight_mcp

logger = logging.getLogger(__name__)


class FlightAgent(BaseAgent):
    """Agent for flight queries backed by the Aliyun API Market."""

    def __init__(self):
        """Initialize flight agent."""
        super().__init__(
            name="Flight Agent",
            description="提供航班搜索与航班详情查询（数据来源：阿里云 API 市场）",
            version="2.0.0",
        )

        self.register_skill(
            Skill(
                name="search_flights",
                description="搜索可用航班",
                tags=["flight", "search"],
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
        max_segments: Optional[int] = None,
    ) -> Dict[str, Any]:
        """搜索可用航班。"""
        return await flight_mcp.search_flights(
            departure, arrival, date, passengers, max_segments
        )

    async def skill_get_flight_detail(
        self, flight_no: str, date: str
    ) -> Dict[str, Any]:
        """获取航班详细信息。"""
        return await flight_mcp.get_flight_detail(flight_no, date)


# Global instance
flight_agent = FlightAgent()
