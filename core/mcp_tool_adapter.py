"""Adapt MCP Server tools into LangChain ``StructuredTool`` objects.

流程：
1. 通过 ``MCPClient`` 连接真正的 MCP Server；
2. 调用 ``list_tools`` 拿到工具列表（由 ``@mcp.tool()`` 注册）；
3. 把每个 MCP 工具的 JSON Schema 转成 Pydantic 模型；
4. 包装为 LangChain Tool，供 ``create_agent(tools=...)`` 使用。

Agent 的大模型会自动决定调用哪个 MCP 工具、传什么参数。
"""

import logging
from typing import Any, Dict, Iterable, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import Field, create_model

from core.mcp_client import MCPClient, python_mcp_client

logger = logging.getLogger(__name__)


class MCPToolAdapter:
    """Wrap MCP tools as LangChain tools tied to a live MCP client."""

    def __init__(self, client: MCPClient) -> None:
        self.client = client
        self._tools: List[StructuredTool] = []
        self._schema_cache: Dict[str, Any] = {}

    async def load_tools(self) -> List[StructuredTool]:
        """Connect (if needed) and dynamically build LangChain tools."""
        if not self.client.session:
            await self.client.connect_to_server()

        tools_response = await self.client.list_tools()
        self._tools = []

        for mcp_tool in tools_response.tools:
            args_schema = self._json_schema_to_pydantic(
                mcp_tool.name, mcp_tool.inputSchema or {}
            )
            self._schema_cache[mcp_tool.name] = args_schema

            async def _call(_tool_name: str = mcp_tool.name, **kwargs: Any) -> str:
                clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}
                return await self.client.call_tool(_tool_name, clean_kwargs)

            tool = StructuredTool.from_function(
                coroutine=_call,
                name=mcp_tool.name,
                description=mcp_tool.description or f"MCP tool: {mcp_tool.name}",
                args_schema=args_schema,
            )
            self._tools.append(tool)
            logger.info("Loaded MCP tool: %s", mcp_tool.name)

        return self._tools

    @staticmethod
    def _json_schema_to_pydantic(tool_name: str, json_schema: Dict[str, Any]):
        """Convert an MCP ``inputSchema`` (JSON Schema) into a Pydantic model."""
        properties = json_schema.get("properties", {}) or {}
        required = set(json_schema.get("required", []) or [])

        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": List[Any],
            "object": Dict[str, Any],
        }

        field_definitions: Dict[str, Any] = {}
        for prop_name, prop_schema in properties.items():
            prop_schema = prop_schema or {}

            prop_type = prop_schema.get("type")
            if not prop_type:
                # 兼容 anyOf / oneOf / $ref 等复杂 schema
                variants = prop_schema.get("anyOf") or prop_schema.get("oneOf") or []
                for variant in variants:
                    if variant.get("type") and variant.get("type") != "null":
                        prop_type = variant.get("type")
                        break

            py_type = type_map.get(prop_type, str)
            description = prop_schema.get("description", "")

            if prop_name in required:
                field_definitions[prop_name] = (
                    py_type,
                    Field(..., description=description),
                )
            else:
                default = prop_schema.get("default")
                field_definitions[prop_name] = (
                    Optional[py_type],
                    Field(default, description=description),
                )

        return create_model(f"{tool_name}_args", **field_definitions)


class MCPToolset:
    """A bundle of MCP clients plus their LangChain tools.

    The MCP clients must stay alive for the tools to work; call :meth:`close`
    when the hosting agent shuts down.
    """

    def __init__(self, clients: List[MCPClient], tools: List[StructuredTool]) -> None:
        self.clients = clients
        self.tools = tools

    async def close(self) -> None:
        """Close all MCP client sessions."""
        for client in self.clients:
            await client.close()
        self.clients = []
        self.tools = []

    @classmethod
    async def create(cls, modules: Iterable[str]) -> "MCPToolset":
        """Connect to one or more MCP server modules and load all tools."""
        clients: List[MCPClient] = []
        tools: List[StructuredTool] = []
        try:
            for module in modules:
                client = python_mcp_client(module)
                await client.connect_to_server()
                adapter = MCPToolAdapter(client)
                tools.extend(await adapter.load_tools())
                clients.append(client)
        except Exception:
            for client in clients:
                await client.close()
            raise
        return cls(clients, tools)


async def build_mcp_tools(module: str) -> List[StructuredTool]:
    """Convenience helper returning tools for a single MCP server module.

    Note: the underlying MCP client stays alive via the returned tools only
    while the event loop and subprocess survive. For long-lived agents prefer
    :class:`MCPToolset`, which keeps an explicit reference for cleanup.
    """
    toolset = await MCPToolset.create([module])
    return toolset.tools
