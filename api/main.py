"""FastAPI main application."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import chat_router, agent_router
from configs.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting SmartVoyage API...")
    logger.info(f"LLM: {settings.openai_model} at {settings.openai_base_url}")
    logger.info(f"Registry: {settings.registry_url}")
    logger.info("Agents: %s", settings.agent_base_urls)
    logger.info("数据库由 Itinerary Agent 通过 db MCP Server 管理")

    yield

    logger.info("Shutting down SmartVoyage API...")


# Create FastAPI app
app = FastAPI(
    title="SmartVoyage API",
    description="SmartVoyage 智能旅行助手 API - 基于 A2A 协议的多智能体系统",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat_router)
app.include_router(agent_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "SmartVoyage API",
        "version": "1.0.0",
        "description": "智能旅行助手 API",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# Run with: uvicorn api.main:app --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.api_gateway_port,
    )
