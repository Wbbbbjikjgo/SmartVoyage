"""Agent API routes for A2A protocol."""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from orchestrator.agent_network import agent_network

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/")
async def list_agents() -> List[Dict[str, Any]]:
    """
    List all registered agents.

    Returns:
        List of agent info
    """
    return agent_network.list_agents()


@router.get("/{agent_name}/card")
async def get_agent_card(agent_name: str) -> Dict[str, Any]:
    """
    Get agent card for A2A protocol.

    Args:
        agent_name: Agent name

    Returns:
        Agent card
    """
    card = agent_network.get_agent_card(agent_name)
    if not card:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")
    return card


@router.post("/{agent_name}/invoke")
async def invoke_agent(
    agent_name: str,
    skill: str,
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Invoke an agent's skill.

    Args:
        agent_name: Agent name
        skill: Skill name
        parameters: Skill parameters

    Returns:
        Skill execution result
    """
    result = await agent_network.invoke_agent(agent_name, skill, parameters)
    return result


@router.get("/.well-known/agent-card.json")
async def gateway_agent_card() -> Dict[str, Any]:
    """
    Gateway agent card for A2A protocol discovery.

    Returns:
        Gateway agent card
    """
    return {
        "name": "SmartVoyage Gateway",
        "description": "SmartVoyage 智能旅行助手网关，提供天气查询、机票酒店预订、行程规划等服务",
        "version": "1.0.0",
        "url": "http://localhost:8000",
        "skills": [
            {
                "name": "weather_query",
                "description": "查询天气信息",
                "tags": ["weather"],
            },
            {
                "name": "flight_booking",
                "description": "查询和预订机票",
                "tags": ["flight", "booking"],
            },
            {
                "name": "hotel_booking",
                "description": "查询和预订酒店",
                "tags": ["hotel", "booking"],
            },
            {
                "name": "itinerary_planning",
                "description": "规划旅行行程",
                "tags": ["itinerary", "planning"],
            },
        ],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "agents": agent_network.list_agents(),
    }
