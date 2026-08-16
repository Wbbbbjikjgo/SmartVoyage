"""Train Agent - handles high-speed rail / train ticket queries."""

import logging
from typing import Any, Dict
from .base_agent import BaseAgent, AgentCard, Skill
from mcp_servers.train_mcp import train_mcp

logger = logging.getLogger(__name__)


class TrainAgent(BaseAgent):
    """Agent for train ticket queries backed by the Aliyun API Market."""

    def __init__(self):
        """Initialize train agent."""
        super().__init__(
            name="Train Agent",
            description="提供高铁/火车票查询服务（数据来源：阿里云 API 市场）",
            version="1.0.0",
        )

        self.register_skill(
            Skill(
                name="search_trains",
                description="搜索高铁/火车票",
                tags=["train", "rail", "search"],
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

    async def skill_search_trains(
        self,
        start: str,
        end: str,
        date: str = "",
        is_high_speed: int = 0,
    ) -> Dict[str, Any]:
        """搜索高铁/火车票。"""
        return await train_mcp.search_trains(start, end, date, is_high_speed)


# Global instance
train_agent = TrainAgent()
