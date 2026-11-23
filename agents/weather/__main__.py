"""Weather A2A Agent 服务入口：描述 AgentCard 并暴露 HTTP URL。"""

import logging

from a2a.types import AgentSkill

from agents.server import build_agent_card, serve_agent
from agents.weather.agent_executor import WeatherAgentExecutor
from configs.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> None:
    """Start the Weather A2A agent."""
    host = settings.agent_host
    port = settings.weather_agent_port
    url = f"http://{host}:{port}"

    skills = [
        AgentSkill(
            id="get_current_weather",
            name="实况天气",
            description="查询指定城市当前的真实实况天气",
            tags=["天气", "实况"],
            examples=["北京现在天气怎么样", "上海今天气温多少度"],
        ),
        AgentSkill(
            id="get_forecast",
            name="天气预报",
            description="查询指定城市未来几天的真实天气预报（最多 4 天）",
            tags=["天气", "预报"],
            examples=["北京未来三天天气", "上海明天会下雨吗"],
        ),
    ]

    card = build_agent_card(
        name="Weather Agent",
        description="提供真实城市实况天气与天气预报查询（数据来源：高德开放平台）",
        url=url,
        skills=skills,
    )
    serve_agent(WeatherAgentExecutor(), card, host, port)


if __name__ == "__main__":
    main()
