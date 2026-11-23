"""Train A2A AgentExecutor.

大模型 + 真实 MCP 工具（阿里云 API 市场火车票接口）。
"""

from agents.base_executor import ToolAwareAgentExecutor


class TrainAgentExecutor(ToolAwareAgentExecutor):
    """A2A executor for train ticket queries."""

    agent_display_name = "火车票 Agent"
    mcp_modules = ["mcp_servers.train_mcp"]
    temperature = 0.1
    system_prompt = """你是 SmartVoyage 的专业火车票/高铁助手。

工作规则：
1. 必须调用 MCP 工具 search_trains 获取真实车次数据。
2. 严禁编造车次、时间、席别或票价；工具返回错误时如实说明（例如缺少 AppCode 或接口不可用）。
3. 查询需要出发站、到达站，日期可选；信息不全时先询问用户。
4. 用简洁的中文列出车次号、类型、发到时间、历时和参考票价。"""
