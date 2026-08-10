"""Agent router for intelligent task routing."""

import logging
from typing import Dict, Any, Tuple, Optional
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
        result = await self.network.invoke_agent(agent_name, skill_name, slots)

        return {
            "success": True,
            "agent": agent_name,
            "intent": intent_result.intent.value,
            "confidence": intent_result.confidence,
            "slots": slots,
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
