"""Lightweight A2A Agent Registry server.

Agent 启动后向本服务注册自己的 Agent Card 地址并定时发送心跳；主 Agent /
网关通过 ``GET /.well-known/agents`` 发现所有在线 Agent 的 URL，再以标准
A2A 协议访问它们。

启动方式::

    python -m registry.server
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from configs.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SmartVoyage A2A Registry",
    description="A2A Agent 注册与发现中心",
    version="1.0.0",
)

_lock = threading.Lock()
_registry: Dict[str, Dict[str, Any]] = {}


class AgentRegistration(BaseModel):
    """Registration payload sent by each A2A agent."""

    name: str = Field(..., description="Agent 唯一名称")
    url: str = Field(..., description="Agent 的 A2A HTTP 地址")
    description: str = ""
    skills: List[Dict[str, Any]] = Field(default_factory=list)
    interval: int = Field(default=30, description="心跳间隔（秒）")


def _is_alive(entry: Dict[str, Any]) -> bool:
    return (time.time() - entry.get("last_seen", 0)) <= settings.registry_ttl


def _public_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": entry["name"],
        "url": entry["url"],
        "description": entry.get("description", ""),
        "skills": entry.get("skills", []),
        "last_seen": entry.get("last_seen", 0),
    }


@app.post("/register")
async def register(payload: AgentRegistration) -> Dict[str, Any]:
    """Register or refresh an agent (heartbeat uses the same endpoint)."""
    with _lock:
        _registry[payload.name] = {
            "name": payload.name,
            "url": payload.url.rstrip("/"),
            "description": payload.description,
            "skills": payload.skills,
            "last_seen": time.time(),
        }
    logger.info("Registered agent %s -> %s", payload.name, payload.url)
    return {"ok": True, "name": payload.name}


@app.post("/heartbeat/{name}")
async def heartbeat(name: str) -> Dict[str, Any]:
    """Refresh an agent's last-seen timestamp."""
    with _lock:
        entry = _registry.get(name)
        if not entry:
            raise HTTPException(status_code=404, detail=f"Agent not registered: {name}")
        entry["last_seen"] = time.time()
    return {"ok": True}


@app.post("/unregister/{name}")
async def unregister(name: str) -> Dict[str, Any]:
    """Remove an agent from the registry."""
    with _lock:
        _registry.pop(name, None)
    return {"ok": True}


@app.get("/.well-known/agents")
async def list_agents() -> List[Dict[str, Any]]:
    """List all currently alive agents (A2A discovery endpoint)."""
    now = time.time()
    with _lock:
        expired = [
            name for name, entry in _registry.items()
            if now - entry.get("last_seen", 0) > settings.registry_ttl
        ]
        for name in expired:
            _registry.pop(name, None)
        return [_public_entry(entry) for entry in _registry.values()]


@app.get("/agents/{name}")
async def get_agent(name: str) -> Dict[str, Any]:
    """Get a single registered agent by name."""
    with _lock:
        entry = _registry.get(name)
        if not entry or not _is_alive(entry):
            raise HTTPException(status_code=404, detail=f"Agent not found: {name}")
        return _public_entry(entry)


@app.get("/health")
async def health() -> Dict[str, Any]:
    """Health check."""
    return {"status": "healthy", "agents": len(_registry)}


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.registry_port,
        log_level="info",
    )
