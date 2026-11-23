"""Base A2A AgentExecutor: LLM + real MCP tools.

每个 Agent 都遵循同一套真实逻辑：

1. 启动时（首次请求时）通过 ``MCPToolset`` 以 stdio 启动并连接 MCP Server；
2. 用 ``MCPToolAdapter`` 把 MCP 工具转换为 LangChain Tool；
3. 把工具交给本 Agent 自己的大模型（DeepSeek）形成可自主决策的 Agent；
4. 大模型自行选择工具、读取真实数据并生成回答；
5. 通过 A2A 协议把最终文本作为 Artifact 返回给调用方。

不做任何模拟数据降级：任何错误都会作为明确的错误文本返回。
"""

import asyncio
import logging
from typing import Any, List, Optional

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Part, TextPart, UnsupportedOperationError
from a2a.utils import completed_task, new_artifact, new_task
from a2a.utils.errors import ServerError

from core.llm import get_chat_llm
from core.mcp_tool_adapter import MCPToolset

logger = logging.getLogger(__name__)


def _content_to_text(content: Any) -> str:
    """Convert an LLM message content (str or content blocks) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        return "".join(parts).strip()
    return str(content)


class ToolAwareAgentExecutor(AgentExecutor):
    """A2A executor backed by an LLM and one or more real MCP servers."""

    agent_display_name: str = "Agent"
    mcp_modules: List[str] = []
    system_prompt: str = ""
    temperature: float = 0.2

    def __init__(self) -> None:
        self._toolset: Optional[MCPToolset] = None
        self._load_error: Optional[str] = None
        self._lock = asyncio.Lock()

    async def _ensure_tools(self) -> None:
        """Lazily start MCP servers and load their tools (once per process)."""
        if self._toolset is not None or self._load_error is not None:
            return

        async with self._lock:
            if self._toolset is not None or self._load_error is not None:
                return
            try:
                self._toolset = await MCPToolset.create(self.mcp_modules)
                logger.info(
                    "Agent %s loaded %d MCP tools: %s",
                    self.agent_display_name,
                    len(self._toolset.tools),
                    [tool.name for tool in self._toolset.tools],
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to start MCP servers for %s", self.agent_display_name)
                self._load_error = f"MCP 工具加载失败: {exc}"

    async def _run_agent(self, user_input: str) -> str:
        """Run the LLM agent with all real MCP tools and return its answer."""
        await self._ensure_tools()
        if self._load_error:
            return self._load_error

        try:
            llm = get_chat_llm(temperature=self.temperature)
        except Exception as exc:  # noqa: BLE001
            return f"大模型不可用: {exc}"

        from langchain.agents import create_agent

        agent = create_agent(
            model=llm,
            tools=self._toolset.tools if self._toolset else [],
            system_prompt=self.system_prompt,
        )
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": user_input}]}
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent %s LLM/tool execution failed", self.agent_display_name)
            return f"{self.agent_display_name} 执行失败：{exc}"

        messages = result.get("messages", [])
        if not messages:
            return "Agent 未生成任何回复。"
        return _content_to_text(messages[-1].content)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute an A2A task and return the final artifact."""
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        user_input = context.get_user_input().strip()
        if not user_input:
            answer = "未收到有效的文本请求。"
        else:
            try:
                answer = await self._run_agent(user_input)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Agent %s execute failed", self.agent_display_name)
                answer = f"{self.agent_display_name} 执行失败：{exc}"

        artifact = new_artifact(
            parts=[Part(root=TextPart(text=answer))],
            name=f"{self.agent_display_name}结果",
        )
        await event_queue.enqueue_event(
            completed_task(
                task.id,
                task.context_id,
                [artifact],
                [context.message] if context.message else [],
            )
        )

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Any:
        """Cancellation is not supported by these agents."""
        raise ServerError(error=UnsupportedOperationError())

    async def shutdown(self) -> None:
        """Close all MCP client sessions."""
        if self._toolset is not None:
            await self._toolset.close()
            self._toolset = None
