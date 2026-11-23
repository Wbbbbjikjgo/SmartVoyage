"""Standard A2A client used by the main agent to call remote agents by URL."""

import logging
import uuid
from typing import Any, Optional

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    AgentCard,
    JSONRPCErrorResponse,
    Message,
    MessageSendParams,
    Part,
    Role,
    SendMessageRequest,
    Task,
    TextPart,
)
from a2a.utils import get_message_text

from configs.settings import settings

logger = logging.getLogger(__name__)


async def fetch_agent_card(base_url: str, timeout: float = 10.0) -> AgentCard:
    """Resolve an AgentCard from ``/.well-known/agent-card.json``."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resolver = A2ACardResolver(httpx_client=client, base_url=base_url)
        return await resolver.get_agent_card()


def _text_from_parts(parts: list) -> str:
    """Extract text from A2A parts."""
    texts = []
    for part in parts or []:
        root = getattr(part, "root", part)
        text = getattr(root, "text", None)
        if text:
            texts.append(str(text))
    return "\n".join(texts).strip()


def _extract_response_text(root: Any) -> str:
    """Extract the final text from an A2A Task or Message response."""
    if isinstance(root, JSONRPCErrorResponse):
        error = root.error
        message = getattr(error, "message", None) or str(error)
        return f"远程 Agent 执行失败：{message}"

    # a2a-sdk 0.3.x 的 send_message 返回 JSON-RPC 响应包装，真正的 Task/Message
    # 位于 ``root.result`` 中。
    nested = getattr(root, "result", None)
    if nested is not None and nested is not root:
        return _extract_response_text(nested)

    if isinstance(root, Message):
        return get_message_text(root).strip()

    if isinstance(root, Task):
        texts = []
        for artifact in root.artifacts or []:
            text = _text_from_parts(artifact.parts)
            if text:
                texts.append(text)
        if texts:
            return "\n".join(texts).strip()

        if root.status and root.status.message:
            text = get_message_text(root.status.message)
            if text:
                return text.strip()

        for message in reversed(root.history or []):
            text = get_message_text(message)
            if text:
                return text.strip()
        return ""

    text = getattr(root, "text", None)
    return str(text).strip() if text else ""


async def call_agent(
    base_url: str,
    text: str,
    timeout: Optional[float] = None,
) -> str:
    """Send a text message to a remote A2A agent and return its final text.

    Args:
        base_url: Agent 的 A2A HTTP 地址。
        text: 要发送给远程 Agent 的文本。
        timeout: 超时时间（秒），默认读取 ``A2A_TIMEOUT``。

    Returns:
        远程 Agent 返回的最终文本。
    """
    timeout = timeout or settings.a2a_timeout

    async with httpx.AsyncClient(timeout=timeout) as client:
        resolver = A2ACardResolver(httpx_client=client, base_url=base_url)
        card = await resolver.get_agent_card()

        a2a_client = A2AClient(httpx_client=client, agent_card=card)
        message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=text))],
            messageId=f"msg-{uuid.uuid4().hex}",
        )
        request = SendMessageRequest(
            id=f"req-{uuid.uuid4().hex}",
            params=MessageSendParams(message=message),
        )

        response = await a2a_client.send_message(request)
        answer = _extract_response_text(response.root)
        logger.info(
            "A2A call finished: agent=%s url=%s chars=%d",
            card.name,
            base_url,
            len(answer),
        )
        return answer
