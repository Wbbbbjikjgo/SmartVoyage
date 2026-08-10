"""Weather Agent - handles weather-related queries."""

import logging
from typing import Dict, Any
from .base_agent import BaseAgent, AgentCard, Skill
from mcp_servers.weather_mcp import weather_mcp

logger = logging.getLogger(__name__)


class WeatherAgent(BaseAgent):
    """Agent for weather queries using QWeather API."""

    def __init__(self):
        """Initialize weather agent."""
        super().__init__(
            name="Weather Agent",
            description="提供全球各地的实时天气信息和预报，支持按城市和日期查询",
            version="1.0.0",
        )

        # Register skills
        self.register_skill(
            Skill(
                name="get_current_weather",
                description="获取指定城市的当前天气",
                tags=["weather", "forecast"],
            )
        )
        self.register_skill(
            Skill(
                name="get_forecast",
                description="获取指定城市的天气预报",
                tags=["weather", "forecast"],
            )
        )
        self.register_skill(
            Skill(
                name="get_air_quality",
                description="获取指定城市的空气质量数据",
                tags=["weather", "air_quality"],
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
        """
        Handle incoming task request.

        Args:
            task: Task request with 'skill' and 'parameters'

        Returns:
            Task result
        """
        skill_name = task.get("skill")
        parameters = task.get("parameters", {})

        if not skill_name:
            return {"error": True, "message": "No skill specified"}

        return await self.execute_skill(skill_name, parameters)

    async def skill_get_current_weather(self, location: str) -> Dict[str, Any]:
        """
        Get current weather for a location.

        Args:
            location: City name

        Returns:
            Weather data
        """
        return await weather_mcp.get_current_weather(location)

    async def skill_get_forecast(
        self,
        location: str,
        days: int = 3,
    ) -> Dict[str, Any]:
        """
        Get weather forecast.

        Args:
            location: City name
            days: Number of forecast days

        Returns:
            Forecast data
        """
        return await weather_mcp.get_forecast(location, days)

    async def skill_get_air_quality(self, location: str) -> Dict[str, Any]:
        """
        Get air quality data.

        Args:
            location: City name

        Returns:
            Air quality data
        """
        return await weather_mcp.get_air_quality(location)


# Global instance
weather_agent = WeatherAgent()
