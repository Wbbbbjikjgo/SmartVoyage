"""Hotel A2A Agent 服务入口：描述 AgentCard 并暴露 HTTP URL。"""

import logging

from a2a.types import AgentSkill

from agents.hotel.agent_executor import HotelAgentExecutor
from agents.server import build_agent_card, serve_agent
from configs.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> None:
    """Start the Hotel A2A agent."""
    host = settings.agent_host
    port = settings.hotel_agent_port
    url = f"http://{host}:{port}"

    skills = [
        AgentSkill(
            id="search_hotels",
            name="搜索酒店",
            description="搜索指定城市的真实酒店（高德 POI）",
            tags=["酒店", "搜索"],
            examples=["北京有什么酒店推荐", "上海外滩附近的酒店"],
        ),
        AgentSkill(
            id="get_hotel_detail",
            name="酒店详情",
            description="查询指定酒店的真实详细信息",
            tags=["酒店", "详情"],
            examples=["查一下北京饭店的地址和电话"],
        ),
        AgentSkill(
            id="search_attractions",
            name="搜索景点",
            description="搜索指定城市的真实景点（高德 POI）",
            tags=["景点", "搜索"],
            examples=["成都有哪些好玩的景点", "杭州西湖附近景点"],
        ),
    ]

    card = build_agent_card(
        name="Hotel Agent",
        description="提供真实酒店与景点查询服务（数据来源：高德开放平台）",
        url=url,
        skills=skills,
    )
    serve_agent(HotelAgentExecutor(), card, host, port)


if __name__ == "__main__":
    main()
