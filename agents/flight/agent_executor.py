"""Flight A2A AgentExecutor.

大模型 + 真实 MCP 工具（阿里云 API 市场航班接口）。
"""

from agents.base_executor import ToolAwareAgentExecutor


class FlightAgentExecutor(ToolAwareAgentExecutor):
    """A2A executor for flight queries."""

    agent_display_name = "航班 Agent"
    mcp_modules = ["mcp_servers.flight_mcp"]
    temperature = 0.1
    system_prompt = """你是 SmartVoyage 的专业航班助手。

工作规则：
1. 必须调用 MCP 工具获取真实航班数据：按航线查询用 search_flights，按航班号查询用 get_flight_detail。
2. 严禁编造航班号、时间、价格或余票；工具返回错误时如实说明（例如缺少 AppCode 或接口不可用）。
3. 查询航线需要出发城市、到达城市和日期；信息不全时先向用户询问，不要猜测。
4. 用简洁的中文列出关键结果（航班号、航司、起降时间、时长、价格），可给出 1-2 条建议。"""
