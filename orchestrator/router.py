"""主 Agent 路由器：意图识别后，通过 A2A 协议调用远程 Agent 的 URL。

当必填槽位缺失时，不直接丢弃请求，而是：
1. 把当前任务存入会话的 ``pending_task``（interrupt）；
2. 向用户追问缺失的信息；
3. 用户补充后自动 merge 槽位并 resume 原任务。

槽位的必填规则与提取逻辑统一由 ``core.slot_filler`` 提供。
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.prompts import ChatPromptTemplate

from configs.settings import settings
from core.context_manager import context_manager
from core.intent_recognizer import intent_recognizer
from core.llm import get_chat_llm
from core.slot_filler import (
    SKILL_PARAMETERS,
    SLOT_EXAMPLES,
    SLOT_LABELS,
    missing_slots,
    slot_filler,
    slot_present,
)
from models.schemas import IntentResult, IntentType
from orchestrator.a2a_client import call_agent
from orchestrator.agent_directory import resolve_agent_url, static_agents
from orchestrator.workflows import travel_workflow

logger = logging.getLogger(__name__)

_CANCEL_WORDS = ("取消", "算了", "不查了", "不用了", "退出", "cancel", "stop")
_EMPTY_VALUES = (None, "", [], {})


class AgentRouter:
    """Route a user request to a remote A2A agent selected by intent."""

    def __init__(self) -> None:
        self.intent_recognizer = intent_recognizer
        self.slot_filler = slot_filler

        self.intent_to_agent: Dict[IntentType, str] = {
            IntentType.WEATHER_QUERY: "weather",
            IntentType.FLIGHT_BOOKING: "flight",
            IntentType.TRAIN_BOOKING: "train",
            IntentType.HOTEL_BOOKING: "hotel",
            IntentType.ITINERARY_PLANNING: "itinerary",
        }

        self.intent_to_skill: Dict[IntentType, str] = {
            IntentType.WEATHER_QUERY: "get_current_weather",
            IntentType.FLIGHT_BOOKING: "search_flights",
            IntentType.TRAIN_BOOKING: "search_trains",
            IntentType.HOTEL_BOOKING: "search_hotels",
            IntentType.ITINERARY_PLANNING: "plan_itinerary",
        }

        self.slot_mapping: Dict[str, Dict[str, str]] = {
            "weather": {"destination": "location"},
            "hotel": {
                "destination": "location",
                "date": "check_in",
                "guests": "guests",
            },
            "flight": {
                "destination": "arrival",
                "guests": "passengers",
            },
            "train": {
                "departure": "start",
                "destination": "end",
            },
        }

    # ================================================================
    # 参数准备
    # ================================================================

    def _prepare_parameters(
        self,
        agent_name: str,
        skill_name: str,
        slots: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Map slots into the parameters accepted by the skill.

        只为 MCP 工具真正接受的参数赋值，不为缺失字段编造默认值。
        """
        params = dict(slots)
        duration_hint = params.get("duration")

        mapping = self.slot_mapping.get(agent_name, {})
        for slot_key, param_name in mapping.items():
            if slot_key == param_name:
                continue
            if slot_key in params and param_name not in params:
                params[param_name] = params.pop(slot_key)
            elif slot_key in params:
                params.pop(slot_key)

        accepted = SKILL_PARAMETERS.get(skill_name)
        if accepted:
            params = {k: v for k, v in params.items() if k in accepted}

        if skill_name == "get_forecast" and "days" not in params and duration_hint:
            params["days"] = duration_hint

        if skill_name == "search_trains":
            # 0 表示不限高铁；这是工具语义默认值，不是用户数据
            params.setdefault("is_high_speed", 0)

        return params

    # ================================================================
    # 远程调用
    # ================================================================

    async def _invoke_remote(self, agent_name: str, prompt: str) -> Tuple[str, str]:
        """Resolve the agent URL and call it through the A2A protocol."""
        url = await resolve_agent_url(agent_name)
        if not url:
            raise RuntimeError(f"未找到 Agent「{agent_name}」的 URL")
        answer = await call_agent(url, prompt, timeout=settings.a2a_timeout)
        return url, answer

    @staticmethod
    def _build_agent_prompt(
        user_input: str,
        intent: IntentType,
        skill: str,
        parameters: Dict[str, Any],
    ) -> str:
        """Compose the task prompt sent to the remote agent."""
        return (
            f"用户原始请求：{user_input}\n"
            f"识别到的意图：{intent.value}\n"
            f"建议使用的技能：{skill}\n"
            f"结构化参数：{json.dumps(parameters, ensure_ascii=False)}\n\n"
            "请调用你可用的 MCP 工具获取真实数据后回答。"
            "严禁编造任何数据；如果工具返回错误，请如实说明原因。"
        )

    # ================================================================
    # 缺失槽位：interrupt + 追问
    # ================================================================

    def _ask_for_slots(
        self,
        session_id: Optional[str],
        intent_result: IntentResult,
        agent_name: str,
        skill_name: str,
        slots: Dict[str, Any],
        missing: List[str],
        original_input: str,
    ) -> Dict[str, Any]:
        """Persist the pending task and ask the user for missing slots."""
        pending = {
            "intent": intent_result.intent.value,
            "confidence": intent_result.confidence,
            "agent": agent_name,
            "skill": skill_name,
            "slots": dict(slots),
            "original_input": original_input,
            "missing": list(missing),
        }
        if session_id:
            context_manager.set_pending_task(session_id, pending)

        labels = [SLOT_LABELS.get(name, name) for name in missing]
        next_slot = missing[0]
        next_label = SLOT_LABELS.get(next_slot, next_slot)
        example = SLOT_EXAMPLES.get(next_slot)
        example_text = f"，例如：{example}" if example else ""

        if len(missing) == 1:
            question = f"还需要你补充「{next_label}」{example_text}。"
        else:
            question = (
                f"还缺少以下信息：{'、'.join(labels)}。"
                f"请先补充「{next_label}」{example_text}。"
            )
        question += "（回复“取消”可放弃本次查询）"

        logger.info("Interrupt: missing slots=%s, session=%s", missing, session_id)
        return {
            "success": True,
            "agent": agent_name,
            "intent": intent_result.intent.value,
            "confidence": intent_result.confidence,
            "slots": slots,
            "skill": skill_name,
            "missing_slots": missing,
            "needs_input": True,
            "question": question,
            "data": {
                "message": question,
                "needs_input": True,
                "missing_slots": missing,
                "slots": slots,
            },
        }

    # ================================================================
    # 主路由
    # ================================================================

    async def route(
        self,
        user_input: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Route a request, resuming an interrupted task when necessary."""
        pending = context_manager.get_pending_task(session_id) if session_id else None
        if pending:
            return await self._resume(user_input, session_id, pending)

        intent_result = await self.intent_recognizer.recognize_with_fallback(user_input)
        logger.info(
            "Intent=%s confidence=%s", intent_result.intent, intent_result.confidence
        )

        slots = self.slot_filler.fill_slots(user_input, intent_result.slots)
        logger.info("Slots=%s", slots)

        if intent_result.intent == IntentType.GENERAL_QA:
            return await self._handle_general_qa(user_input, intent_result, slots)

        if intent_result.intent == IntentType.ITINERARY_PLANNING:
            return await self._handle_itinerary(
                user_input, intent_result, slots, session_id
            )

        agent_name = self.intent_to_agent.get(intent_result.intent)
        if not agent_name:
            return {
                "error": True,
                "message": f"未找到处理该意图的 Agent: {intent_result.intent}",
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
                "slots": slots,
            }

        skill_name = self._select_skill(intent_result.intent, user_input, slots)
        return await self._dispatch_single(
            user_input, intent_result, slots, agent_name, skill_name, session_id
        )

    async def route_to_agent(self, agent_name: str, text: str) -> Dict[str, Any]:
        """Directly call a remote agent by logical name (no intent recognition)."""
        try:
            url, answer = await self._invoke_remote(agent_name, text)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "agent": agent_name, "message": str(exc)}
        return {
            "success": True,
            "agent": agent_name,
            "url": url,
            "data": {"answer": answer},
        }

    # ================================================================
    # resume 逻辑
    # ================================================================

    async def _resume(
        self,
        user_input: str,
        session_id: Optional[str],
        pending: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge the user's follow-up answer into the pending task."""
        if any(word in user_input.lower() for word in _CANCEL_WORDS):
            if session_id:
                context_manager.clear_pending_task(session_id)
            return {
                "success": True,
                "agent": pending.get("agent"),
                "intent": pending.get("intent"),
                "cancelled": True,
                "data": {"message": "已取消本次查询。"},
            }

        slots = dict(pending.get("slots") or {})
        skill_name = pending.get("skill", "")
        missing_before = missing_slots(slots, skill_name)

        if len(missing_before) == 1:
            # 只有一个缺失槽位时，把用户的短回答直接映射到该槽位，
            # 避免“北京”被误当成目的地而污染其他字段。
            slot_name = missing_before[0]
            value = self.slot_filler.extract_slot_value(slot_name, user_input)
            if value not in _EMPTY_VALUES:
                slots[slot_name] = value
        else:
            new_slots = self.slot_filler.fill_slots(user_input, {})
            for key, value in new_slots.items():
                if value not in _EMPTY_VALUES:
                    slots[key] = value
            for slot_name in list(missing_slots(slots, skill_name)):
                value = self.slot_filler.extract_slot_value(slot_name, user_input)
                if value not in _EMPTY_VALUES:
                    slots[slot_name] = value

        intent = IntentType(pending.get("intent", IntentType.GENERAL_QA.value))
        intent_result = IntentResult(
            intent=intent,
            confidence=float(pending.get("confidence", 1.0)),
            slots=slots,
        )
        still_missing = missing_slots(slots, skill_name)
        if still_missing:
            return self._ask_for_slots(
                session_id,
                intent_result,
                pending.get("agent", ""),
                skill_name,
                slots,
                still_missing,
                pending.get("original_input", user_input),
            )

        if session_id:
            context_manager.clear_pending_task(session_id)

        original_input = pending.get("original_input") or user_input
        if pending.get("agent") == "itinerary":
            return await self._route_itinerary(original_input, intent_result, slots)

        return await self._dispatch_single(
            original_input,
            intent_result,
            slots,
            pending.get("agent", ""),
            skill_name,
            session_id,
        )

    # ================================================================
    # 单 Agent 调度
    # ================================================================

    async def _dispatch_single(
        self,
        user_input: str,
        intent_result: IntentResult,
        slots: Dict[str, Any],
        agent_name: str,
        skill_name: str,
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        """Validate slots, ask for missing ones, or call the remote agent."""
        if skill_name == "get_flight_detail" and "flight_no" not in slots:
            flight_no = self._extract_flight_no(user_input)
            if flight_no:
                slots["flight_no"] = flight_no
        elif skill_name == "get_hotel_detail" and "hotel_name" not in slots:
            hotel_name = self._extract_hotel_name(user_input)
            if hotel_name:
                slots["hotel_name"] = hotel_name

        missing = missing_slots(slots, skill_name)
        if missing:
            return self._ask_for_slots(
                session_id, intent_result, agent_name, skill_name, slots, missing,
                user_input,
            )

        parameters = self._prepare_parameters(agent_name, skill_name, slots)
        prompt = self._build_agent_prompt(
            user_input, intent_result.intent, skill_name, parameters
        )

        try:
            url, answer = await self._invoke_remote(agent_name, prompt)
        except Exception as exc:  # noqa: BLE001
            logger.exception("调用远程 Agent 失败: %s", agent_name)
            if session_id:
                context_manager.clear_pending_task(session_id)
            return {
                "success": False,
                "agent": agent_name,
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
                "slots": slots,
                "message": (
                    f"调用 {agent_name} Agent 失败：{exc}。"
                    "请确认该 Agent 服务已启动。"
                ),
                "data": {"error": True, "message": str(exc)},
            }

        return {
            "success": True,
            "agent": agent_name,
            "intent": intent_result.intent.value,
            "confidence": intent_result.confidence,
            "slots": slots,
            "skill": skill_name,
            "url": url,
            "data": {"answer": answer, "url": url},
        }

    # ================================================================
    # 行程规划
    # ================================================================

    async def plan(
        self,
        user_input: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Force an itinerary-planning request (used by ``/api/chat/plan``)."""
        if session_id and context_manager.get_pending_task(session_id):
            return await self.route(user_input, session_id=session_id)

        intent_result = await self.intent_recognizer.recognize_with_fallback(user_input)
        intent_result = IntentResult(
            intent=IntentType.ITINERARY_PLANNING,
            confidence=intent_result.confidence,
            slots=intent_result.slots,
        )
        slots = self.slot_filler.fill_slots(user_input, intent_result.slots)
        return await self._handle_itinerary(
            user_input, intent_result, slots, session_id
        )

    async def _handle_itinerary(
        self,
        user_input: str,
        intent_result: IntentResult,
        slots: Dict[str, Any],
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        """Validate itinerary slots, ask for missing ones, then plan."""
        missing = missing_slots(slots, "plan_itinerary")
        if missing:
            return self._ask_for_slots(
                session_id,
                intent_result,
                "itinerary",
                "plan_itinerary",
                slots,
                missing,
                user_input,
            )
        return await self._route_itinerary(user_input, intent_result, slots)

    async def _route_itinerary(
        self,
        user_input: str,
        intent_result: IntentResult,
        slots: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run the multi-agent itinerary workflow with complete slots."""
        destination = slots.get("destination") or slots.get("location")
        start_date = slots.get("start_date") or slots.get("date")
        duration_raw = slots.get("duration")
        if not destination or not start_date or duration_raw in _EMPTY_VALUES:
            return {
                "success": False,
                "agent": "itinerary",
                "intent": intent_result.intent.value,
                "message": "行程规划缺少目的地、出发日期或天数。",
                "data": {"error": True},
            }

        try:
            duration = int(duration_raw)
        except (TypeError, ValueError):
            duration = 1

        try:
            guests = int(slots.get("guests") or 1)
        except (TypeError, ValueError):
            guests = 1

        result = await travel_workflow.execute(
            user_id=int(slots.get("user_id") or 1),
            destination=str(destination),
            start_date=str(start_date),
            duration=duration,
            departure=slots.get("departure"),
            budget=slots.get("budget"),
            guests=guests,
            user_input=user_input,
        )

        return {
            "success": bool(result.get("success")),
            "agent": "itinerary",
            "intent": intent_result.intent.value,
            "confidence": intent_result.confidence,
            "slots": slots,
            "data": {
                "answer": result.get("answer", ""),
                "details": result,
            },
        }

    # ================================================================
    # 技能选择
    # ================================================================

    def _select_skill(
        self,
        intent: IntentType,
        user_input: str,
        slots: Dict[str, Any],
    ) -> str:
        """Choose the most appropriate skill under a given intent."""
        if intent == IntentType.WEATHER_QUERY:
            forecast_kw = ("明天", "后天", "未来", "预报", "几天", "下周", "本周", "最近")
            if any(kw in user_input for kw in forecast_kw) or "days" in slots:
                return "get_forecast"
            return "get_current_weather"

        if intent == IntentType.FLIGHT_BOOKING:
            if slot_present(slots, "flight_no") or self._extract_flight_no(user_input):
                return "get_flight_detail"
            return "search_flights"

        if intent == IntentType.TRAIN_BOOKING:
            return "search_trains"

        if intent == IntentType.HOTEL_BOOKING:
            attraction_kw = ("景点", "好玩", "游玩", "攻略", "旅游", "景区", "风景")
            if any(kw in user_input for kw in attraction_kw):
                return "search_attractions"
            detail_kw = ("详情", "电话", "设施", "评分", "地址")
            if self._extract_hotel_name(user_input) and any(kw in user_input for kw in detail_kw):
                return "get_hotel_detail"
            return "search_hotels"

        if intent == IntentType.ITINERARY_PLANNING:
            return "plan_itinerary"

        return self.intent_to_skill.get(intent, "")

    def _extract_flight_no(self, text: str) -> Optional[str]:
        """Extract a flight number such as CA1234 / MU8218."""
        return self.slot_filler._extract_flight_no(text)

    def _extract_hotel_name(self, text: str) -> Optional[str]:
        """Extract a hotel name such as「希尔顿酒店」."""
        return self.slot_filler._extract_hotel_name(text)

    # ================================================================
    # 通用问答
    # ================================================================

    async def _handle_general_qa(
        self,
        user_input: str,
        intent_result: IntentResult,
        slots: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Reply to chit-chat with the LLM (no fabricated data involved)."""
        reply = await self._generate_general_reply(user_input)
        return {
            "success": True,
            "agent": "general",
            "intent": IntentType.GENERAL_QA.value,
            "confidence": intent_result.confidence,
            "slots": slots,
            "data": {"message": reply},
        }

    async def _generate_general_reply(self, user_input: str) -> str:
        """Generate a natural chit-chat reply with the LLM."""
        fallback = (
            "我是 SmartVoyage 智能旅行助手，可以帮您查询天气、查询机票/高铁票/酒店、"
            "规划旅行行程。请问有什么可以帮您的？"
        )
        try:
            llm = get_chat_llm(temperature=0.7)
            prompt = ChatPromptTemplate.from_messages([
                (
                    "system",
                    "你是 SmartVoyage 智能旅行助手，热情友好。用户可能只是闲聊或打招呼，"
                    "请顺着用户的话自然回应（一两句话即可），并在合适时机自然地提示你能帮忙做的事："
                    "查询天气、查询/预订机票、高铁票、酒店、规划旅行行程。回答简洁自然，用中文。",
                ),
                ("human", "{input}"),
            ])
            response = await llm.ainvoke(prompt.format_messages(input=user_input))
            content = response.content.strip()
            return content or fallback
        except Exception as exc:  # noqa: BLE001
            logger.warning("通用问答 LLM 调用失败: %s", exc)
            return fallback

    # ================================================================
    # 调试信息
    # ================================================================

    def get_routing_info(self) -> Dict[str, Any]:
        """Return routing configuration and statically configured agents."""
        return {
            "intent_to_agent": {k.value: v for k, v in self.intent_to_agent.items()},
            "intent_to_skill": {k.value: v for k, v in self.intent_to_skill.items()},
            "agents": static_agents(),
        }


agent_router = AgentRouter()
