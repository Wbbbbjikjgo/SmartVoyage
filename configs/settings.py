"""Application settings and configuration management."""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Configuration (DeepSeek / OpenAI compatible)
    openai_api_key: str = Field(..., description="OpenAI/DeepSeek API key")
    openai_base_url: str = Field(
        default="https://api.deepseek.com",
        description="OpenAI API base URL"
    )
    openai_model: str = Field(
        default="deepseek-chat",
        description="LLM model name"
    )

    # Weather API (QWeather)
    qweather_api_key: str = Field(..., description="QWeather API key")
    qweather_base_url: str = Field(
        default="https://devapi.qweather.com",
        description="QWeather API base URL"
    )
    qweather_mock_mode: bool = Field(
        default=True,
        description="Use mock weather data instead of real QWeather API"
    )

    # MySQL Configuration
    mysql_host: str = Field(default="localhost")
    mysql_port: int = Field(default=3306)
    mysql_user: str = Field(default="root")
    mysql_password: str = Field(..., description="MySQL password")
    mysql_database: str = Field(default="smartvoyage")

    # Redis Configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )

    # Elasticsearch Configuration
    es_url: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch URL"
    )

    # Agent Ports
    weather_agent_port: int = Field(default=5001)
    flight_agent_port: int = Field(default=5002)
    hotel_agent_port: int = Field(default=5003)
    itinerary_agent_port: int = Field(default=5004)

    # MCP Server Ports
    weather_mcp_port: int = Field(default=5010)
    flight_mcp_port: int = Field(default=5011)
    hotel_mcp_port: int = Field(default=5012)
    db_mcp_port: int = Field(default=5013)

    # API Gateway
    api_gateway_port: int = Field(default=8000)

    # Streamlit
    streamlit_port: int = Field(default=8501)

    @property
    def mysql_dsn(self) -> str:
        """Generate MySQL connection DSN."""
        return (
            f"mysql+mysqlconnector://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    class Config:
        """Pydantic config."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
