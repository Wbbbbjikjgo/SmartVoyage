"""Agent router for intelligent task routing."""

import logging
from typing import Dict, Any, List, Tuple, Optional
from models.schemas import IntentType, IntentResult
from core.intent_recognizer import intent_recognizer
from core.slot_filler import slot_filler
from orchestrator.agent_network import agent_network

logger = logging.getLogger(__name__)


class AgentRouter:
    """Routes tasks to appropriate agents based on intent."""

    def __init__(self):
        """Initialize agent router."""
        self.network = agent_network
        self.intent_recognizer = intent_recognizer
        self.slot_filler = slot_filler

        # Intent to agent mapping
        self.intent_to_agent: Dict[IntentType, str] = {
            IntentType.WEATHER_QUERY: "weather",
            IntentType.FLIGHT_BOOKING: "flight",
            IntentType.HOTEL_BOOKING: "hotel",
            IntentType.ITINERARY_PLANNING: "itinerary",
        }

        # Intent to skill mapping
        self.intent_to_skill: Dict[IntentType, str] = {
            IntentType.WEATHER_QUERY: "get_current_weather",
            IntentType.FLIGHT_BOOKING: "search_flights",
            IntentType.HOTEL_BOOKING: "search_hotels",
            IntentType.ITINERARY_PLANNING: "create_itinerary",
        }

        # Slot name mapping per agent (slot key -> skill parameter name)
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
        }

        # Required parameters per skill (to filter out extra slots)
        self.skill_required_params: Dict[str, List[str]] = {
            "get_current_weather": ["location"],
            "search_flights": ["departure", "arrival", "date", "passengers"],
            "search_hotels": ["location", "check_in", "check_out", "guests"],
            "create_itinerary": ["user_id", "destination", "start_date", "duration", "budget"],
        }

    def _prepare_parameters(
        self,
        agent_name: str,
        skill_name: str,
        slots: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Prepare parameters for a skill call by mapping slot names.

        Args:
            agent_name: Agent name
            skill_name: Skill name
            slots: Extracted slots

        Returns:
            Mapped parameters dict
        """
        params = dict(slots)

        # Keep duration aside before filtering (used for hotel check_out default)
        duration_hint = params.get("duration")

        # Apply slot name mapping
        mapping = self.slot_mapping.get(agent_name, {})
        for slot_key, param_name in mapping.items():
            if slot_key in params and param_name not in params:
                params[param_name] = params.pop(slot_key)
            elif slot_key in params:
                params.pop(slot_key)

        # Filter to only parameters accepted by the skill
        required = self.skill_required_params.get(skill_name)
        if required:
            params = {k: v for k, v in params.items() if k in required}

        # Fill sensible defaults for date-related params so users are not forced to repeat
        from datetime import date, timedelta
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        if skill_name == "search_flights" and not params.get("date"):
            params["date"] = tomorrow
            params.setdefault("_defaults_used", []).append("date=明天")

        if skill_name == "search_hotels":
            if not params.get("check_in"):
                params["check_in"] = tomorrow
                params.setdefault("_defaults_used", []).append("check_in=明天")
            if not params.get("check_out"):
                try:
                    check_in = date.fromisoformat(params["check_in"])
                    duration = int(duration_hint or 2)
                    params["check_out"] = (check_in + timedelta(days=duration)).isoformat()
                    params.setdefault("_defaults_used", []).append(f"check_out={params['check_out']}")
                except (ValueError, TypeError):
                    params["check_out"] = (date.today() + timedelta(days=3)).isoformat()

        if skill_name == "create_itinerary":
            if not params.get("start_date"):
                params["start_date"] = tomorrow
                params.setdefault("_defaults_used", []).append("start_date=明天")
            if not params.get("duration"):
                params["duration"] = 3
                params.setdefault("_defaults_used", []).append("duration=3天")

        return params

    async def route(self, user_input: str) -> Dict[str, Any]:
        """
        Route user input to appropriate agent.

        Args:
            user_input: User's natural language input

        Returns:
            Routing result with agent response
        """
        # Step 1: Recognize intent
        intent_result = await self.intent_recognizer.recognize_with_fallback(user_input)
        logger.info(f"Recognized intent: {intent_result.intent} (confidence: {intent_result.confidence})")

        # Step 2: Fill slots
        slots = self.slot_filler.fill_slots(user_input, intent_result.slots)
        logger.info(f"Filled slots: {slots}")

        # Step 3: Route to agent
        if intent_result.intent == IntentType.GENERAL_QA:
            # Handle general QA directly
            return await self._handle_general_qa(user_input, intent_result, slots)

        agent_name = self.intent_to_agent.get(intent_result.intent)
        if not agent_name:
            return {
                "error": True,
                "message": f"No agent found for intent: {intent_result.intent}",
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
                "slots": slots,
            }

        # Step 4: Invoke agent
        skill_name = self.intent_to_skill.get(intent_result.intent)
        parameters = self._prepare_parameters(agent_name, skill_name, slots)

        # Check required parameters
        missing = [
            p for p in self.skill_required_params.get(skill_name, [])
            if p not in parameters and p not in ("passengers", "guests", "budget", "user_id")
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

        # Default user_id for itinerary creation
        if skill_name == "create_itinerary" and "user_id" not in parameters:
            parameters["user_id"] = 1

        # Strip internal metadata before invoking the skill
        defaults_used = parameters.pop("_defaults_used", None)

        result = await self.network.invoke_agent(agent_name, skill_name, parameters)

        return {
            "success": True,
            "agent": agent_name,
            "intent": intent_result.intent.value,
            "confidence": intent_result.confidence,
            "slots": slots,
            "defaults_used": defaults_used,
            "data": result,
        }

    async def route_to_agent(
        self,
        agent_name: str,
        skill: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Directly route to a specific agent and skill.

        Args:
            agent_name: Agent name
            skill: Skill name
            parameters: Skill parameters

        Returns:
            Agent response
        """
        return await self.network.invoke_agent(agent_name, skill, parameters)

    async def _handle_general_qa(
        self,
        user_input: str,
        intent_result: IntentResult,
        slots: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle general QA without specific agent.

        Args:
            user_input: User input
            intent_result: Intent result
            slots: Extracted slots

        Returns:
            Response dict
        """
        # For now, return a simple response
        # In production, this could use LLM to generate a response
        return {
            "success": True,
            "agent": "general",
            "intent": IntentType.GENERAL_QA.value,
            "confidence": intent_result.confidence,
            "slots": slots,
            "data": {
                "message": "我是 SmartVoyage 智能旅行助手，可以帮您查询天气、预订机票酒店、规划行程。请问有什么可以帮您的？",
            },
        }

    def get_routing_info(self) -> Dict[str, Any]:
        """
        Get routing configuration info.

        Returns:
            Routing info dict
        """
        return {
            "intent_to_agent": {
                k.value: v for k, v in self.intent_to_agent.items()
            },
            "intent_to_skill": {
                k.value: v for k, v in self.intent_to_skill.items()
            },
            "agents": self.network.list_agents(),
        }


# Global instance
agent_router = AgentRouter()
