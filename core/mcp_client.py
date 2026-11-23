"""MCP (Model Context Protocol) client over stdio.

与参考实现保持一致：通过 stdio 启动并连接真正的 MCP Server，调用其通过
``@mcp.tool()`` 注册的工具。Agent 不直接 import 工具实现，而是通过本客户端
经 MCP 协议访问。
"""

import logging
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

# 项目根目录（供 MCP Server 子进程 locate configs / mcp_servers 包）
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class MCPClient:
    """MCP client that connects to a stdio MCP server and calls its tools."""

    def __init__(
        self,
        command: str,
        args: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        """Initialize the client.

        Args:
            command: 启动服务器的命令（通常为 ``sys.executable``）。
            args: 命令参数（如 ``["-m", "mcp_servers.weather_mcp"]``）。
            cwd: 子进程工作目录（默认项目根目录）。
            env: 额外环境变量。
        """
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.command = command
        self.args = args
        self.cwd = cwd or str(PROJECT_ROOT)
        self.env = env or {}

    def _build_env(self) -> Dict[str, str]:
        """Build the subprocess environment (inherit + UTF-8 + project root)."""
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = os.pathsep.join(
            [str(PROJECT_ROOT), env.get("PYTHONPATH", "")]
        ).strip(os.pathsep)
        env.update(self.env)
        return env

    async def connect_to_server(self) -> None:
        """Start the MCP server and complete the initialization handshake."""
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self._build_env(),
            cwd=self.cwd,
            encoding="utf-8",
        )
        stdio, write = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(stdio, write)
        )
        await self.session.initialize()
        logger.info(
            "MCP client connected: %s %s", self.command, " ".join(self.args)
        )

    async def list_tools(self) -> Any:
        """Return the raw MCP tool definitions."""
        if not self.session:
            await self.connect_to_server()
        return await self.session.list_tools()

    async def call_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """Call a tool on the MCP server and return its text content."""
        if not self.session:
            await self.connect_to_server()

        result = await self.session.call_tool(tool_name, tool_args)
        texts = []
        for item in result.content:
            text = getattr(item, "text", None)
            if text is not None:
                texts.append(str(text))
        joined = "\n".join(texts)
        if getattr(result, "isError", False):
            return f"[MCP tool error] {joined}"
        return joined

    async def __aenter__(self) -> "MCPClient":
        await self.connect_to_server()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the session and terminate the server subprocess."""
        try:
            await self.exit_stack.aclose()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            logger.debug("Error while closing MCP client", exc_info=True)
        finally:
            self.session = None


def python_mcp_client(module: str) -> MCPClient:
    """Convenience factory: connect to ``python -m <module>`` via stdio."""
    return MCPClient(sys.executable, ["-m", module])
