"""聊天 API 路由：主 Agent 意图识别 + 远程 A2A Agent 调用。

槽位缺失时路由层会“中断”并追问；前端保持同一个 ``session_id`` 继续发送，
路由层会自动 resume 原任务。
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.context_manager import context_manager
from orchestrator.router import agent_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """聊天请求模型。"""

    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """聊天响应模型。"""

    message: str
    intent: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    session_id: str
    needs_input: Optional[bool] = None
    missing_slots: Optional[List[str]] = None


def _extract_answer(data: Dict[str, Any]) -> str:
    """Pull the human-readable answer out of a routed result."""
    if not isinstance(data, dict):
        return str(data)

    for key in ("answer", "message"):
        value = data.get(key)
        if value:
            return str(value)

    details = data.get("details")
    if isinstance(details, dict):
        for key in ("answer", "message"):
            value = details.get(key)
            if value:
                return str(value)
    return ""


def _compose_message(result: Dict[str, Any]) -> str:
    """Build the final chat message from a routed result."""
    data = result.get("data") or {}

    if result.get("cancelled"):
        return data.get("message", "已取消本次查询。")

    if result.get("needs_input") or result.get("missing_slots"):
        return data.get("message", result.get("question", "请补充更多信息。"))

    if result.get("success") is False:
        return result.get("message") or "调用远程 Agent 失败，请检查服务状态。"

    if result.get("agent") == "general":
        return data.get("message", "我是 SmartVoyage 智能旅行助手。")

    answer = _extract_answer(data)
    if answer:
        return answer
    if result.get("message"):
        return str(result["message"])
    return "Agent 未返回有效内容，请检查对应 Agent 的日志。"


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """通用聊天入口：意图识别后调用对应的远程 A2A Agent。"""
    session_id = request.session_id or context_manager.create_session()
    context_manager.add_message(session_id, "user", request.message)

    try:
        result = await agent_router.route(request.message, session_id=session_id)
        message = _compose_message(result)
        context_manager.add_message(session_id, "assistant", message)
        return ChatResponse(
            message=message,
            intent=result.get("intent"),
            data=result.get("data") or result,
            session_id=session_id,
            needs_input=result.get("needs_input"),
            missing_slots=result.get("missing_slots"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("聊天接口出错")
        message = f"抱歉，处理您的请求时出现错误：{exc}"
        context_manager.add_message(session_id, "assistant", message)
        return ChatResponse(message=message, session_id=session_id)


@router.post("/plan", response_model=ChatResponse)
async def plan_travel(request: ChatRequest) -> ChatResponse:
    """多 Agent 协作的旅行规划接口（同样支持缺失槽位追问/resume）。"""
    session_id = request.session_id or context_manager.create_session()
    context_manager.add_message(session_id, "user", request.message)

    try:
        result = await agent_router.plan(request.message, session_id=session_id)
        message = _compose_message(result)
        context_manager.add_message(session_id, "assistant", message)
        return ChatResponse(
            message=message,
            intent=result.get("intent", "itinerary_planning"),
            data=result.get("data") or result,
            session_id=session_id,
            needs_input=result.get("needs_input"),
            missing_slots=result.get("missing_slots"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("规划接口出错")
        message = f"规划行程时出现错误：{exc}"
        context_manager.add_message(session_id, "assistant", message)
        return ChatResponse(message=message, session_id=session_id)


@router.get("/session/{session_id}")
async def get_session_info(session_id: str) -> Dict[str, Any]:
    """获取会话信息。"""
    session = context_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return context_manager.get_session_summary(session_id)
