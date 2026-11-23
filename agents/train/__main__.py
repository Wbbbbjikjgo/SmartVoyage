"""Train A2A Agent 服务入口：描述 AgentCard 并暴露 HTTP URL。"""

import logging

from a2a.types import AgentSkill

from agents.server import build_agent_card, serve_agent
from agents.train.agent_executor import TrainAgentExecutor
from configs.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> None:
    """Start the Train A2A agent."""
    host = settings.agent_host
    port = settings.train_agent_port
    url = f"http://{host}:{port}"

    skills = [
        AgentSkill(
            id="search_trains",
            name="查询火车票",
            description="查询指定线路的真实高铁/火车票",
            tags=["火车", "高铁", "查询"],
            examples=["杭州到北京的高铁票", "明天郑州到洛阳的火车"],
        ),
    ]

    card = build_agent_card(
        name="Train Agent",
        description="提供真实高铁/火车票查询服务（数据来源：阿里云 API 市场）",
        url=url,
        skills=skills,
    )
    serve_agent(TrainAgentExecutor(), card, host, port)


if __name__ == "__main__":
    main()
