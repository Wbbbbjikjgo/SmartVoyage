"""Hotel A2A AgentExecutor.

大模型 + 真实 MCP 工具（高德 POI：酒店 / 景点）。
"""

from agents.base_executor import ToolAwareAgentExecutor


class HotelAgentExecutor(ToolAwareAgentExecutor):
    """A2A executor for hotel and attraction queries."""

    agent_display_name = "酒店 Agent"
    mcp_modules = ["mcp_servers.hotel_mcp"]
    temperature = 0.2
    system_prompt = """你是 SmartVoyage 的专业酒店与景点助手。

工作规则：
1. 必须调用 MCP 工具获取真实数据：酒店列表用 search_hotels，酒店详情用 get_hotel_detail，景点用 search_attractions。
2. 严禁编造酒店、景点、评分、地址、电话或价格。高德 POI 不提供实时房价与设施，若用户询问，请如实说明该数据不可用。
3. 工具返回错误时如实说明原因。
4. 用简洁的中文列出推荐结果（名称、位置、评分、电话），并给出简短建议。"""
