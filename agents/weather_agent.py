"""Weather Agent - handles weather-related queries."""

import logging
from typing import Dict, Any
from .base_agent import BaseAgent, AgentCard, Skill
from mcp_servers.weather_mcp import weather_mcp

logger = logging.getLogger(__name__)


class WeatherAgent(BaseAgent):
    """Agent for weather queries backed by the AMap (高德) weather API."""

    def __init__(self):
        """Initialize weather agent."""
        super().__init__(
            name="Weather Agent",
            description="提供城市实况天气与天气预报查询（数据来源：高德开放平台）",
            version="2.0.0",
        )

        self.register_skill(
            Skill(
                name="get_current_weather",
                description="获取指定城市的实况天气",
                tags=["weather", "current"],
            )
        )
        self.register_skill(
            Skill(
                name="get_forecast",
                description="获取指定城市的天气预报（未来最多4天）",
                tags=["weather", "forecast"],
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

    async def skill_get_current_weather(self, location: str) -> Dict[str, Any]:
        """获取指定城市的实况天气。"""
        return await weather_mcp.get_current_weather(location)

    async def skill_get_forecast(
        self, location: str, days: int = 3
    ) -> Dict[str, Any]:
        """获取指定城市的天气预报。"""
        return await weather_mcp.get_forecast(location, days)


# Global instance
weather_agent = WeatherAgent()
