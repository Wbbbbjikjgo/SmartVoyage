"""Flight A2A Agent 服务入口：描述 AgentCard 并暴露 HTTP URL。"""

import logging

from a2a.types import AgentSkill

from agents.flight.agent_executor import FlightAgentExecutor
from agents.server import build_agent_card, serve_agent
from configs.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> None:
    """Start the Flight A2A agent."""
    host = settings.agent_host
    port = settings.flight_agent_port
    url = f"http://{host}:{port}"

    skills = [
        AgentSkill(
            id="search_flights",
            name="查询航班",
            description="查询指定航线和日期的真实航班信息",
            tags=["航班", "查询"],
            examples=["查询明天北京到上海的机票", "5月1日广州飞北京有哪些航班"],
        ),
        AgentSkill(
            id="get_flight_detail",
            name="航班详情",
            description="查询指定航班号的真实详细信息",
            tags=["航班", "详情"],
            examples=["MU5100 这个航班几点起飞", "查一下 CA1234 的详情"],
        ),
    ]

    card = build_agent_card(
        name="Flight Agent",
        description="提供真实航班查询服务（数据来源：阿里云 API 市场）",
        url=url,
        skills=skills,
    )
    serve_agent(FlightAgentExecutor(), card, host, port)


if __name__ == "__main__":
    main()
