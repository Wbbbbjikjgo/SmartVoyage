"""Agent discovery API routes (backed by the A2A registry)."""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from orchestrator.a2a_client import fetch_agent_card
from orchestrator.agent_directory import list_agents as discover_agents
from orchestrator.agent_directory import resolve_agent_url
from orchestrator.router import agent_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentInvokeRequest(BaseModel):
    """Direct A2A invocation payload."""

    text: str


@router.get("/.well-known/agent-card.json")
async def gateway_agent_card() -> Dict[str, Any]:
    """Gateway AgentCard for A2A discovery."""
    agents = await discover_agents()
    return {
        "name": "SmartVoyage Gateway",
        "description": "SmartVoyage 智能旅行助手网关，负责意图识别并调用远程 A2A Agent",
        "version": "1.0.0",
        "url": "http://localhost:8000",
        "skills": [
            {"name": "weather_query", "description": "查询天气信息", "tags": ["weather"]},
            {"name": "flight_query", "description": "查询航班信息", "tags": ["flight"]},
            {"name": "train_query", "description": "查询火车票", "tags": ["train"]},
            {"name": "hotel_query", "description": "查询酒店/景点", "tags": ["hotel"]},
            {"name": "itinerary_planning", "description": "规划旅行行程", "tags": ["itinerary"]},
        ],
        "capabilities": {"streaming": False, "pushNotifications": False},
        "agents": agents,
    }


@router.get("/")
async def list_agents() -> List[Dict[str, Any]]:
    """List discovered remote agents."""
    return await discover_agents()


@router.get("/{agent_name}/card")
async def get_agent_card(agent_name: str) -> Dict[str, Any]:
    """Fetch a remote agent's real AgentCard."""
    url = await resolve_agent_url(agent_name)
    if not url:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")
    try:
        card = await fetch_agent_card(url)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail=f"无法获取 {agent_name} 的 AgentCard: {exc}"
        ) from exc
    return card.model_dump(by_alias=True, exclude_none=True)


@router.post("/{agent_name}/invoke")
async def invoke_agent(agent_name: str, payload: AgentInvokeRequest) -> Dict[str, Any]:
    """Directly call a remote agent through the A2A protocol."""
    return await agent_router.route_to_agent(agent_name, payload.text)
