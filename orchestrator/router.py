"""主 Agent 路由器：意图识别后，通过 A2A 协议调用远程 Agent 的 URL。

真正的执行逻辑位于各远程 Agent（各自拥有大模型 + MCP 工具）。主 Agent
只负责：意图识别 → 槽位填充 → 选择 Agent/Skill → 解析 URL → A2A 调用。
"""

import json
import logging
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.prompts import ChatPromptTemplate

from configs.settings import settings
from core.intent_recognizer import intent_recognizer
from core.llm import get_chat_llm
from core.slot_filler import slot_filler
from models.schemas import IntentResult, IntentType
from orchestrator.a2a_client import call_agent
from orchestrator.agent_directory import resolve_agent_url, static_agents
from orchestrator.workflows import travel_workflow

logger = logging.getLogger(__name__)


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

        self.skill_required_params: Dict[str, List[str]] = {
            "get_current_weather": ["location"],
            "get_forecast": ["location"],
            "search_flights": ["departure", "arrival", "date", "passengers"],
            "get_flight_detail": ["flight_no", "date"],
            "search_trains": ["start", "end", "date", "is_high_speed"],
            "search_hotels": ["location", "check_in", "check_out", "guests"],
            "get_hotel_detail": ["hotel_name"],
            "search_attractions": ["location"],
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
        """Map/validate slots into the parameters expected by the skill."""
        params = dict(slots)
        duration_hint = params.get("duration")

        mapping = self.slot_mapping.get(agent_name, {})
        for slot_key, param_name in mapping.items():
            if slot_key in params and param_name not in params:
                params[param_name] = params.pop(slot_key)
            elif slot_key in params:
                params.pop(slot_key)

        required = self.skill_required_params.get(skill_name)
        if required:
            params = {k: v for k, v in params.items() if k in required}

        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        if skill_name in ("search_flights", "get_flight_detail") and not params.get("date"):
            params["date"] = tomorrow
            params.setdefault("_defaults_used", []).append("date=明天")

        if skill_name == "search_trains":
            if not params.get("date"):
                params["date"] = tomorrow
                params.setdefault("_defaults_used", []).append("date=明天")
            params.setdefault("is_high_speed", 0)

        if skill_name == "search_hotels":
            if not params.get("check_in"):
                params["check_in"] = tomorrow
                params.setdefault("_defaults_used", []).append("check_in=明天")
            if not params.get("check_out"):
                try:
                    check_in = date.fromisoformat(params["check_in"])
                    duration = int(duration_hint or 2)
                    params["check_out"] = (check_in + timedelta(days=duration)).isoformat()
                    params.setdefault("_defaults_used", []).append(
                        f"check_out={params['check_out']}"
                    )
                except (ValueError, TypeError):
                    params["check_out"] = (
                        date.today() + timedelta(days=3)
                    ).isoformat()

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
    # 主路由
    # ================================================================

    async def route(self, user_input: str) -> Dict[str, Any]:
        """Run intent recognition and dispatch to the selected remote agent."""
        intent_result = await self.intent_recognizer.recognize_with_fallback(user_input)
        logger.info(
            "Intent=%s confidence=%s", intent_result.intent, intent_result.confidence
        )

        slots = self.slot_filler.fill_slots(user_input, intent_result.slots)
        logger.info("Slots=%s", slots)

        if intent_result.intent == IntentType.GENERAL_QA:
            return await self._handle_general_qa(user_input, intent_result, slots)

        if intent_result.intent == IntentType.ITINERARY_PLANNING:
            return await self._route_itinerary(user_input, intent_result, slots)

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

        if skill_name == "get_flight_detail":
            slots.setdefault("flight_no", self._extract_flight_no(user_input))
        elif skill_name == "get_hotel_detail":
            slots.setdefault("hotel_name", self._extract_hotel_name(user_input))

        parameters = self._prepare_parameters(agent_name, skill_name, slots)

        missing = [
            param
            for param in self.skill_required_params.get(skill_name, [])
            if param not in parameters
            and param not in ("passengers", "guests", "budget", "user_id")
        ]
        if missing:
            return {
                "success": True,
                "agent": agent_name,
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
                "slots": slots,
                "missing_slots": missing,
                "data": {
                    "message": f"还需要以下信息才能完成查询：{', '.join(missing)}，请补充后重试。",
                },
            }

        defaults_used = parameters.pop("_defaults_used", None)
        prompt = self._build_agent_prompt(
            user_input, intent_result.intent, skill_name, parameters
        )

        try:
            url, answer = await self._invoke_remote(agent_name, prompt)
        except Exception as exc:  # noqa: BLE001
            logger.exception("调用远程 Agent 失败: %s", agent_name)
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
            "defaults_used": defaults_used,
            "data": {"answer": answer, "url": url},
        }

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
            if any(kw in user_input for kw in forecast_kw) or "duration" in slots:
                return "get_forecast"
            return "get_current_weather"

        if intent == IntentType.FLIGHT_BOOKING:
            if self._extract_flight_no(user_input):
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

    @staticmethod
    def _extract_flight_no(text: str) -> Optional[str]:
        """Extract a flight number such as CA1234 / MU8218."""
        match = re.search(r"[A-Za-z]{2}\d{3,4}", text)
        return match.group(0).upper() if match else None

    @staticmethod
    def _extract_hotel_name(text: str) -> Optional[str]:
        """Extract a hotel name such as「希尔顿酒店」."""
        match = re.search(
            r"([\u4e00-\u9fa5A-Za-z0-9]{2,12}(?:酒店|宾馆|饭店|民宿|客栈))", text
        )
        return match.group(1) if match else None

    # ================================================================
    # 行程规划（多 Agent 协作）
    # ================================================================

    async def _route_itinerary(
        self,
        user_input: str,
        intent_result: IntentResult,
        slots: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Route itinerary planning to the multi-agent workflow."""
        destination = slots.get("destination")
        if not destination:
            return {
                "success": True,
                "agent": "itinerary",
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
                "slots": slots,
                "missing_slots": ["destination"],
                "data": {"message": "请告诉我你想去哪个城市，我才能帮你规划行程。"},
            }

        defaults_used = []

        start_date = slots.get("date") or slots.get("start_date")
        if not start_date:
            start_date = (date.today() + timedelta(days=1)).isoformat()
            defaults_used.append("start_date=明天")

        try:
            duration = int(slots.get("duration") or 3)
        except (TypeError, ValueError):
            duration = 3
        if "duration" not in slots:
            defaults_used.append("duration=3天")

        try:
            guests = int(slots.get("guests") or 1)
        except (TypeError, ValueError):
            guests = 1

        result = await travel_workflow.execute(
            user_id=1,
            destination=destination,
            start_date=start_date,
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
            "defaults_used": defaults_used,
            "data": {
                "answer": result.get("answer", ""),
                "details": result,
            },
        }

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
