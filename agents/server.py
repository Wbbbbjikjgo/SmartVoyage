"""Shared helpers to expose an AgentExecutor as a real A2A HTTP service."""

import logging
from contextlib import asynccontextmanager
from typing import List

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agents.base_executor import ToolAwareAgentExecutor
from core.registry_client import start_registration
from configs.settings import settings

logger = logging.getLogger(__name__)


def build_agent_card(
    name: str,
    description: str,
    url: str,
    skills: List[AgentSkill],
) -> AgentCard:
    """Build a standard A2A AgentCard."""
    return AgentCard(
        name=name,
        description=description,
        url=url,
        version="1.0.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=skills,
    )


def serve_agent(
    executor: ToolAwareAgentExecutor,
    card: AgentCard,
    host: str,
    port: int,
) -> None:
    """Start the A2A HTTP server and register the agent in the registry."""
    settings.log_credential_status()

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )
    application = A2AStarletteApplication(
        agent_card=card,
        http_handler=request_handler,
    )

    @asynccontextmanager
    async def lifespan(_app):
        yield
        await executor.shutdown()

    app = application.build(lifespan=lifespan)

    start_registration(
        registry_url=settings.registry_url,
        name=card.name,
        url=card.url,
        description=card.description,
        skills=[
            {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "tags": skill.tags,
            }
            for skill in card.skills
        ],
        interval=settings.registry_heartbeat_interval,
    )

    logger.info("Starting A2A agent '%s' at %s", card.name, card.url)
    uvicorn.run(app, host=host, port=port, log_level="info")
