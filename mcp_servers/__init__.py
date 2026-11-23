"""Real MCP (Model Context Protocol) servers for SmartVoyage.

每个子模块都是一个可独立运行的 stdio MCP Server：

    python -m mcp_servers.weather_mcp
    python -m mcp_servers.flight_mcp
    python -m mcp_servers.train_mcp
    python -m mcp_servers.hotel_mcp
    python -m mcp_servers.db_mcp

Agent 不直接 import 这些服务器，而是通过 ``core.mcp_client`` 以子进程方式
连接，并使用 ``core.mcp_tool_adapter`` 把 MCP 工具包装成 LangChain Tool。
"""
