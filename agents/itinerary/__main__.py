"""Itinerary A2A Agent 服务入口：描述 AgentCard 并暴露 HTTP URL。"""

import logging

from a2a.types import AgentSkill

from agents.itinerary.agent_executor import ItineraryAgentExecutor
from agents.server import build_agent_card, serve_agent
from configs.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> None:
    """Start the Itinerary A2A agent."""
    host = settings.agent_host
    port = settings.itinerary_agent_port
    url = f"http://{host}:{port}"

    skills = [
        AgentSkill(
            id="plan_itinerary",
            name="行程规划",
            description="根据真实天气/酒店/交通数据生成逐日旅行计划",
            tags=["行程", "规划"],
            examples=["帮我规划北京三日游", "根据这些信息生成上海两天行程"],
        ),
        AgentSkill(
            id="create_itinerary",
            name="创建行程",
            description="把行程写入数据库",
            tags=["行程", "数据库"],
            examples=["把北京三日游保存下来"],
        ),
        AgentSkill(
            id="get_user_itineraries",
            name="查询行程",
            description="查询用户的历史行程",
            tags=["行程", "查询"],
            examples=["查看我的行程"],
        ),
    ]

    card = build_agent_card(
        name="Itinerary Agent",
        description="提供行程规划与行程/预订数据库管理服务（MySQL 真实数据）",
        url=url,
        skills=skills,
    )
    serve_agent(ItineraryAgentExecutor(), card, host, port)


if __name__ == "__main__":
    main()
