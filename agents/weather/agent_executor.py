"""Weather A2A AgentExecutor.

大模型 + 真实 MCP 工具（高德天气）：模型会自行决定调用实况天气或天气预报
工具，读取真实数据后生成回答。
"""

from agents.base_executor import ToolAwareAgentExecutor


class WeatherAgentExecutor(ToolAwareAgentExecutor):
    """A2A executor for weather queries."""

    agent_display_name = "天气 Agent"
    mcp_modules = ["mcp_servers.weather_mcp"]
    temperature = 0.1
    system_prompt = """你是 SmartVoyage 的专业天气助手。

工作规则：
1. 必须调用 MCP 工具获取真实天气数据（实况用 get_current_weather，未来天气用 get_forecast）。
2. 严禁编造任何天气数据；工具返回错误时，如实说明错误原因（例如缺少 API Key 或接口不可用）。
3. 根据数据给出简洁、实用的中文回答，包含温度、天气、湿度、风力等关键信息。
4. 如果用户没有指定城市，先礼貌询问城市，不要猜测。"""
