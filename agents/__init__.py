"""A2A Agents for SmartVoyage.

每个子包都是一个独立的 A2A HTTP 服务：

    python -m agents.weather
    python -m agents.flight
    python -m agents.train
    python -m agents.hotel
    python -m agents.itinerary

Agent 内部使用自己的大模型 + 真实 MCP 工具；Agent 之间只通过 A2A HTTP URL
通信，不再进行进程内直接调用。
"""

from .base_executor import ToolAwareAgentExecutor

__all__ = ["ToolAwareAgentExecutor"]
