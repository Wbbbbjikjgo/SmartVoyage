"""Agent discovery: prefer the registry, fall back to configured static URLs."""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from configs.settings import settings

logger = logging.getLogger(__name__)

_CACHE_TTL = 10.0
_cache: Optional[Tuple[float, List[Dict[str, Any]]]] = None


def static_agents() -> List[Dict[str, Any]]:
    """Return the statically configured agents (fallback when registry is down)."""
    descriptions = {
        "weather": "天气查询 Agent",
        "flight": "航班查询 Agent",
        "hotel": "酒店/景点查询 Agent",
        "itinerary": "行程规划与数据库 Agent",
        "train": "火车票查询 Agent",
    }
    return [
        {
            "name": name,
            "url": url,
            "description": descriptions.get(name, ""),
            "skills": [],
            "source": "static",
        }
        for name, url in settings.agent_base_urls.items()
    ]


async def discover_agents(timeout: float = 2.0) -> List[Dict[str, Any]]:
    """Discover online agents from the registry, falling back to static config."""
    global _cache

    now = time.monotonic()
    if _cache is not None and now - _cache[0] < _CACHE_TTL:
        return _cache[1]

    endpoint = f"{settings.registry_url.rstrip('/')}/.well-known/agents"
    agents: Optional[List[Dict[str, Any]]] = None
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(endpoint)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list) and payload:
                for entry in payload:
                    entry["source"] = "registry"
                agents = payload
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Agent 注册中心不可用，使用静态配置: %s", exc)

    result = agents if agents is not None else static_agents()
    _cache = (now, result)
    return result


def _matches(entry_name: str, key: str) -> bool:
    """Match a registry AgentCard name (e.g. 'Weather Agent') to a logical key."""
    return key in (entry_name or "").lower()


async def resolve_agent_url(key: str) -> Optional[str]:
    """Resolve a logical agent key (weather/flight/...) to its A2A URL."""
    key = key.lower()
    for entry in await discover_agents():
        if _matches(entry.get("name", ""), key):
            return entry.get("url")
    return settings.agent_base_urls.get(key)


async def list_agents() -> List[Dict[str, Any]]:
    """Return a merged list of discovered + statically configured agents."""
    discovered = await discover_agents()
    merged: Dict[str, Dict[str, Any]] = {}
    for entry in discovered:
        merged[entry.get("url") or entry.get("name")] = entry
    for entry in static_agents():
        merged.setdefault(entry["url"], entry)
    return list(merged.values())
