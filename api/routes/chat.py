"""
聊天 API 路由
提供 REST API 接口，供前端或外部系统调用

功能：
1. /api/chat/ - 通用聊天入口，自动识别意图并路由到对应的 Agent
2. /api/chat/plan - 专门用于旅行规划的快捷入口
3. /api/chat/session/{session_id} - 获取会话信息
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.dependencies import get_current_session
from orchestrator.router import agent_router
from orchestrator.workflows import travel_workflow
from core.context_manager import context_manager

# 获取日志记录器
logger = logging.getLogger(__name__)


def _format_itinerary(itin: Dict[str, Any]) -> str:
    """把详细行程数据组装成可读的 Markdown 文本。"""
    destination = itin.get("destination", "")
    start_date = itin.get("start_date", "")
    duration = itin.get("duration", 0)
    days = itin.get("days", [])

    lines = [f"已为您规划 **{destination}** {duration} 天行程（{start_date} 起）：\n"]
    for day in days:
        acts = "、".join(day.get("attractions", [])) or "自由活动"
        weather = day.get("weather", "")
        suffix = f"　{weather}" if weather else ""
        lines.append(f"**第{day.get('day')}天（{day.get('date')}）**：{acts}{suffix}")

    hotels = itin.get("hotels", [])
    if hotels:
        top_hotel = hotels[0]
        hotel_name = top_hotel.get("hotel_name", "")
        lines.append(f"\n推荐酒店：{hotel_name} 等 {len(hotels)} 家")

    itinerary_id = itin.get("itinerary_id")
    if itinerary_id:
        lines.append(f"行程已保存，ID：{itinerary_id}")

    return "\n".join(lines)


# ================================================================
# 1. 路由定义
# ================================================================

# 创建 APIRouter 实例，所有路由都以 /api/chat 开头
# tags=["chat"] 用于 API 文档分组
router = APIRouter(prefix="/api/chat", tags=["chat"])


# ================================================================
# 2. 请求/响应模型（Pydantic Schema）
# ================================================================

class ChatRequest(BaseModel):
    """
    聊天请求模型

    前端调用 API 时需要传这两个字段
    """
    message: str                      # 用户输入的消息（必填）
    session_id: Optional[str] = None  # 会话ID（可选，不传则自动创建新会话）


class ChatResponse(BaseModel):
    """
    聊天响应模型

    后端返回给前端的数据格式
    """
    message: str                      # 要显示给用户的回复文本
    intent: Optional[str] = None      # 识别到的意图（如 "flight_booking"）
    data: Optional[Dict[str, Any]] = None  # 附加的结构化数据
    session_id: str                   # 会话ID（前端需保存，用于多轮对话）


# ================================================================
# 3. 主要接口：通用聊天
# ================================================================

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    通用聊天接口（主入口）

    工作流程：
        1. 获取或创建会话
        2. 保存用户消息到上下文
        3. 通过 AgentRouter 路由到对应的 Agent
        4. 根据 Agent 类型生成友好的回复
        5. 保存助手回复到上下文
        6. 返回响应

    Args:
        request: 聊天请求（包含消息和可选会话ID）

    Returns:
        聊天响应（包含回复文本、意图、数据和会话ID）
    """
    # ============================================================
    # 步骤1：获取或创建会话
    # ============================================================
    # 如果前端传了 session_id，就用已有的；否则创建新会话
    session_id = request.session_id or context_manager.create_session()

    # ============================================================
    # 步骤2：保存用户消息到上下文（用于多轮对话记忆）
    # ============================================================
    context_manager.add_message(session_id, "user", request.message)

    try:
        # ============================================================
        # 步骤3：路由到对应的 Agent
        # ============================================================
        # agent_router.route() 会做：
        #   意图识别 → 槽位填充 → 找到对应的 Agent → 执行技能
        result = await agent_router.route(request.message)

        # ============================================================
        # 步骤4：根据返回结果构建回复
        # ============================================================
        if result.get("success"):
            agent_name = result.get("agent", "unknown")
            data = result.get("data", {})

            # -------- 4.1 处理"缺少槽位"的情况 --------
            # 如果 Agent 发现用户缺少必要信息，会返回 missing_slots
            # 这时需要让用户补充信息，而不是执行具体任务
            if result.get("missing_slots"):
                message = data.get("message", "请补充更多信息。")
                context_manager.add_message(session_id, "assistant", message)
                return ChatResponse(
                    message=message,
                    intent=result.get("intent"),
                    data=data,
                    session_id=session_id,
                )

            # -------- 4.2 根据不同的 Agent 生成不同的回复风格 --------

            # 通用问答（闲聊/打招呼）
            if agent_name == "general":
                message = data.get("message", "我是 SmartVoyage 智能旅行助手。")

            # 天气 Agent
            elif agent_name == "weather":
                weather_data = data.get("data", {})
                if weather_data.get("error"):
                    # 查询出错
                    message = f"抱歉，查询天气时出错：{weather_data.get('message')}"
                else:
                    # 提取天气信息，组装成友好回复
                    location = weather_data.get("location", "")
                    temp = weather_data.get("temperature", "")
                    desc = weather_data.get("description", "")
                    message = f"{location}当前天气：{desc}，气温{temp}°C。"

            # 航班 Agent
            elif agent_name == "flight":
                flight_data = data.get("data", {})
                if flight_data.get("error"):
                    message = f"抱歉，查询航班时出错：{flight_data.get('message')}"
                else:
                    total = flight_data.get("total", 0)
                    message = f"为您找到 {total} 个航班。"

            # 高铁/火车票 Agent
            elif agent_name == "train":
                train_data = data.get("data", {})
                if train_data.get("error"):
                    message = f"抱歉，查询火车票时出错：{train_data.get('message')}"
                else:
                    total = train_data.get("total", 0)
                    message = f"为您找到 {total} 趟车次。"

            # 酒店 Agent
            elif agent_name == "hotel":
                hotel_data = data.get("data", {})
                if hotel_data.get("error"):
                    message = f"抱歉，查询酒店时出错：{hotel_data.get('message')}"
                else:
                    total = hotel_data.get("total", 0)
                    message = f"为您找到 {total} 家酒店。"

            # 行程 Agent
            elif agent_name == "itinerary":
                itinerary_data = data.get("data", {})
                if itinerary_data.get("error"):
                    message = f"抱歉，规划行程时出错：{itinerary_data.get('message')}"
                else:
                    message = _format_itinerary(itinerary_data)

            else:
                # 未知 Agent 的兜底回复
                message = "任务已完成。"

            # -------- 4.3 补充默认值提示 --------
            # 如果系统自动填充了默认值（如日期默认为明天），告诉用户
            defaults_used = result.get("defaults_used")
            if defaults_used:
                # 提取默认值的描述文本
                # 例如：["date=明天", "duration=3天"] → "明天、3天"
                defaults_desc = "、".join(
                    d.split("=")[1] if "=" in d else d for d in defaults_used
                )
                message += f"（未指定日期，已默认使用：{defaults_desc}）"

            # ============================================================
            # 步骤5：保存助手回复到上下文
            # ============================================================
            context_manager.add_message(session_id, "assistant", message)

            # ============================================================
            # 步骤6：返回响应
            # ============================================================
            return ChatResponse(
                message=message,
                intent=result.get("intent"),
                data=data,
                session_id=session_id,
            )

        else:
            # -------- 处理失败情况 --------
            message = result.get("message", "处理请求时出错。")
            context_manager.add_message(session_id, "assistant", message)

            return ChatResponse(
                message=message,
                intent=result.get("intent"),
                data=result.get("data"),
                session_id=session_id,
            )

    except Exception as e:
        # ============================================================
        # 异常处理：捕获任何未预期的错误
        # ============================================================
        logger.exception(f"聊天接口出错: {e}")
        error_message = "抱歉，处理您的请求时出现错误，请稍后再试。"
        context_manager.add_message(session_id, "assistant", error_message)

        return ChatResponse(
            message=error_message,
            session_id=session_id,
        )


# ================================================================
# 4. 旅行规划专用接口
# ================================================================

@router.post("/plan", response_model=ChatResponse)
async def plan_travel(request: ChatRequest) -> ChatResponse:
    """
    旅行规划专用接口

    这个接口直接调用 TravelPlanningWorkflow，
    执行完整的旅行规划（查天气→查航班→查酒店→创建行程）

    与通用聊天接口的区别：
        - 通用接口：意图识别 → 单个 Agent
        - 规划接口：直接调用工作流 → 多个 Agent 协作

    Args:
        request: 聊天请求（包含旅行描述）

    Returns:
        包含完整行程规划的响应
    """
    # ============================================================
    # 步骤1：获取或创建会话
    # ============================================================
    session_id = request.session_id or context_manager.create_session()
    context_manager.add_message(session_id, "user", request.message)

    try:
        # ============================================================
        # 步骤2：从用户消息中提取旅行信息
        # ============================================================
        # 通过意图识别 + 槽位填充，从自然语言中提取结构化信息
        from core.intent_recognizer import intent_recognizer
        from core.slot_filler import slot_filler
        from models.schemas import IntentType

        # 识别意图
        intent_result = await intent_recognizer.recognize(request.message)
        # 填充槽位
        slots = slot_filler.fill_slots(request.message, intent_result.slots)

        # -------- 提取各个槽位，并设置默认值 --------
        destination = slots.get("destination", "北京")          # 目的地，默认北京
        start_date = slots.get("date") or slots.get("start_date") or "2026-08-20"  # 日期
        duration = slots.get("duration") or 3                   # 天数，默认3天
        departure = slots.get("departure")                      # 出发城市（可选）
        budget = slots.get("budget")                            # 预算（可选）
        guests = slots.get("guests") or 1                       # 人数，默认1人

        # ============================================================
        # 步骤3：执行旅行规划工作流
        # ============================================================
        # user_id=1 是演示用户的固定ID
        result = await travel_workflow.execute(
            user_id=1,                # 默认用户（演示用）
            destination=destination,
            start_date=start_date,
            duration=duration,
            departure=departure,
            budget=budget,
            guests=guests,
        )

        # ============================================================
        # 步骤4：生成回复
        # ============================================================
        if result.get("success"):
            itinerary_id = result.get("itinerary_id")
            message = f"已为您规划 {result['destination']} 的 {result['duration']} 天行程。"
            if itinerary_id:
                message += f"行程已保存（ID：{itinerary_id}）。"
            context_manager.add_message(session_id, "assistant", message)

            return ChatResponse(
                message=message,
                intent="itinerary_planning",
                data=result,           # 返回完整的行程数据（天气、航班、酒店等）
                session_id=session_id,
            )
        else:
            # 规划失败
            message = f"规划行程时出错：{result.get('error', '未知错误')}"
            context_manager.add_message(session_id, "assistant", message)

            return ChatResponse(
                message=message,
                session_id=session_id,
            )

    except Exception as e:
        logger.exception(f"规划接口出错: {e}")
        return ChatResponse(
            message="规划行程时出现错误。",
            session_id=session_id,
        )


# ================================================================
# 5. 获取会话信息接口
# ================================================================

@router.get("/session/{session_id}")
async def get_session_info(session_id: str) -> Dict[str, Any]:
    """
    获取会话信息

    用于查看某个会话的完整聊天历史和上下文

    Args:
        session_id: 会话ID

    Returns:
        会话摘要信息（包含所有消息历史）

    Raises:
        HTTPException: 如果会话不存在，返回 404
    """
    # 检查会话是否存在
    session = context_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 返回会话摘要
    return context_manager.get_session_summary(session_id)