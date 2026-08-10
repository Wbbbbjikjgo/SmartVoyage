"""Chat API routes."""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.dependencies import get_current_session
from orchestrator.router import agent_router
from orchestrator.workflows import travel_workflow
from core.context_manager import context_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model."""
    message: str
    intent: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    session_id: str


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint for user interactions.

    Args:
        request: Chat request with message and optional session_id

    Returns:
        Chat response with assistant message and data
    """
    # Get or create session
    session_id = request.session_id or context_manager.create_session()

    # Add user message to context
    context_manager.add_message(session_id, "user", request.message)

    try:
        # Route to appropriate agent
        result = await agent_router.route(request.message)

        # Extract response message
        if result.get("success"):
            agent_name = result.get("agent", "unknown")
            data = result.get("data", {})

            # Missing slots prompt - return directly
            if result.get("missing_slots"):
                message = data.get("message", "请补充更多信息。")
                context_manager.add_message(session_id, "assistant", message)
                return ChatResponse(
                    message=message,
                    intent=result.get("intent"),
                    data=data,
                    session_id=session_id,
                )

            # Generate response message based on agent and data
            if agent_name == "general":
                message = data.get("message", "我是 SmartVoyage 智能旅行助手。")
            elif agent_name == "weather":
                weather_data = data.get("data", {})
                if weather_data.get("error"):
                    message = f"抱歉，查询天气时出错：{weather_data.get('message')}"
                else:
                    location = weather_data.get("location", "")
                    temp = weather_data.get("temperature", "")
                    desc = weather_data.get("description", "")
                    message = f"{location}当前天气：{desc}，气温{temp}°C。"
            elif agent_name == "flight":
                flight_data = data.get("data", {})
                if flight_data.get("error"):
                    message = f"抱歉，查询航班时出错：{flight_data.get('message')}"
                else:
                    total = flight_data.get("total", 0)
                    message = f"为您找到 {total} 个航班。"
            elif agent_name == "hotel":
                hotel_data = data.get("data", {})
                if hotel_data.get("error"):
                    message = f"抱歉，查询酒店时出错：{hotel_data.get('message')}"
                else:
                    total = hotel_data.get("total", 0)
                    message = f"为您找到 {total} 家酒店。"
            elif agent_name == "itinerary":
                itinerary_data = data.get("data", {})
                if itinerary_data.get("error"):
                    message = f"抱歉，创建行程时出错：{itinerary_data.get('message')}"
                else:
                    itinerary_id = itinerary_data.get("itinerary_id", "")
                    message = f"行程已创建，行程ID：{itinerary_id}。"
            else:
                message = "任务已完成。"

            # Append default-values notice (e.g. date defaulted to tomorrow)
            defaults_used = result.get("defaults_used")
            if defaults_used:
                defaults_desc = "、".join(
                    d.split("=")[1] if "=" in d else d for d in defaults_used
                )
                message += f"（未指定日期，已默认使用：{defaults_desc}）"

            # Add assistant message to context
            context_manager.add_message(session_id, "assistant", message)

            return ChatResponse(
                message=message,
                intent=result.get("intent"),
                data=data,
                session_id=session_id,
            )
        else:
            # Error case
            message = result.get("message", "处理请求时出错。")
            context_manager.add_message(session_id, "assistant", message)

            return ChatResponse(
                message=message,
                intent=result.get("intent"),
                data=result.get("data"),
                session_id=session_id,
            )

    except Exception as e:
        logger.exception(f"Error in chat endpoint: {e}")
        error_message = "抱歉，处理您的请求时出现错误，请稍后再试。"
        context_manager.add_message(session_id, "assistant", error_message)

        return ChatResponse(
            message=error_message,
            session_id=session_id,
        )


@router.post("/plan", response_model=ChatResponse)
async def plan_travel(request: ChatRequest) -> ChatResponse:
    """
    Travel planning endpoint for complete itinerary.

    Args:
        request: Chat request with travel details

    Returns:
        Chat response with planned itinerary
    """
    session_id = request.session_id or context_manager.create_session()
    context_manager.add_message(session_id, "user", request.message)

    try:
        # Parse travel details from user message via intent recognition + slot filling
        from core.intent_recognizer import intent_recognizer
        from core.slot_filler import slot_filler
        from models.schemas import IntentType

        intent_result = await intent_recognizer.recognize(request.message)
        slots = slot_filler.fill_slots(request.message, intent_result.slots)

        destination = slots.get("destination", "北京")
        start_date = slots.get("date") or slots.get("start_date") or "2026-08-20"
        duration = slots.get("duration") or 3
        departure = slots.get("departure")
        budget = slots.get("budget")
        guests = slots.get("guests") or 1

        result = await travel_workflow.execute(
            user_id=1,  # Default user for demo
            destination=destination,
            start_date=start_date,
            duration=duration,
            departure=departure,
            budget=budget,
            guests=guests,
        )

        if result.get("success"):
            itinerary_id = result.get("itinerary_id")
            message = f"已为您规划 {result['destination']} 的 {result['duration']} 天行程。"
            if itinerary_id:
                message += f"行程已保存（ID：{itinerary_id}）。"
            context_manager.add_message(session_id, "assistant", message)

            return ChatResponse(
                message=message,
                intent="itinerary_planning",
                data=result,
                session_id=session_id,
            )
        else:
            message = f"规划行程时出错：{result.get('error', '未知错误')}"
            context_manager.add_message(session_id, "assistant", message)

            return ChatResponse(
                message=message,
                session_id=session_id,
            )

    except Exception as e:
        logger.exception(f"Error in plan endpoint: {e}")
        return ChatResponse(
            message="规划行程时出现错误。",
            session_id=session_id,
        )


@router.get("/session/{session_id}")
async def get_session_info(session_id: str) -> Dict[str, Any]:
    """
    Get session information.

    Args:
        session_id: Session ID

    Returns:
        Session info
    """
    session = context_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return context_manager.get_session_summary(session_id)
