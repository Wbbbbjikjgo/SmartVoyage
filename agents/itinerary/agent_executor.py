"""Itinerary A2A AgentExecutor.

大模型 + 真实 MCP 工具（MySQL CRUD）。该 Agent 负责：
- 根据其他 Agent 收集到的真实天气/酒店/航班/车次数据生成逐日行程；
- 按需通过数据库工具创建行程、记录预订。
"""

from agents.base_executor import ToolAwareAgentExecutor


class ItineraryAgentExecutor(ToolAwareAgentExecutor):
    """A2A executor for itinerary planning and persistence."""

    agent_display_name = "行程 Agent"
    mcp_modules = ["mcp_servers.db_mcp"]
    temperature = 0.4
    system_prompt = """你是 SmartVoyage 的资深行程规划师，同时负责行程的数据库管理。

工作规则：
1. 规划行程时，只能使用请求中提供的真实数据（天气、景点、酒店、航班、车次），绝不能编造不存在的景点、酒店、航班或车次。
2. 把景点合理分配到每天，结合天气安排室内/户外活动，并给出具体时间、游玩时长与交通方式建议。
3. 若请求要求保存行程（提供了 user_id、目的地、开始日期、天数），先调用 get_user 确认用户存在；不存在则调用 create_user 创建，再调用 create_itinerary 写入数据库。写入失败时如实说明数据库错误，但仍然给出行程文本。
4. 若请求要求查询/更新/取消行程或预订，调用对应的数据库工具。
5. 用结构清晰的中文 Markdown 输出（按天分节）。"""
