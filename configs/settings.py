"""Application settings and configuration management."""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ================================================================
    # LLM Configuration (DeepSeek / OpenAI compatible)
    # ================================================================
    openai_api_key: str = Field(..., description="OpenAI/DeepSeek API key")
    openai_base_url: str = Field(
        default="https://api.deepseek.com",
        description="OpenAI API base URL",
    )
    openai_model: str = Field(
        default="deepseek-chat",
        description="LLM model name",
    )

    # ================================================================
    # AMap Open Platform (高德开放平台) - weather / hotel / geocode
    # ================================================================
    amap_api_key: str = Field(..., description="高德开放平台 Web 服务 API key")
    amap_base_url: str = Field(
        default="https://restapi.amap.com",
        description="高德开放平台 REST API 基础地址",
    )
    weather_mock_mode: bool = Field(
        default=False,
        description="天气查询使用模拟数据（高德免费额度充足，默认真实）",
    )
    hotel_mock_mode: bool = Field(
        default=False,
        description="酒店查询使用模拟数据（高德免费额度充足，默认真实）",
    )

    # ================================================================
    # Aliyun API Market (阿里云 API 市场) - flight / train
    # ================================================================
    aliyun_appcode: str = Field(..., description="阿里云 API 市场 AppCode")
    aliyun_flight_url: str = Field(
        default="https://flightss.market.alicloudapi.com/flight/query",
        description="阿里云航班查询接口地址",
    )
    aliyun_train_url: str = Field(
        default="http://jisutrainf.market.alicloudapi.com/train/station2s",
        description="阿里云火车票查询接口地址",
    )
    flight_mock_mode: bool = Field(
        default=False,
        description="航班查询使用模拟数据（默认开启，保护免费调用额度）",
    )
    train_mock_mode: bool = Field(
        default=False,
        description="火车票查询使用模拟数据（默认开启，保护免费调用额度）",
    )

    # ================================================================
    # MySQL Configuration
    # ================================================================
    mysql_host: str = Field(default="localhost")
    mysql_port: int = Field(default=3306)
    mysql_user: str = Field(default="root")
    mysql_password: str = Field(..., description="MySQL password")
    mysql_database: str = Field(default="smartvoyage")

    # ================================================================
    # Redis Configuration
    # ================================================================
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # ================================================================
    # Elasticsearch Configuration
    # ================================================================
    es_url: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch URL",
    )

    # ================================================================
    # Agent Ports
    # ================================================================
    weather_agent_port: int = Field(default=5001)
    flight_agent_port: int = Field(default=5002)
    hotel_agent_port: int = Field(default=5003)
    itinerary_agent_port: int = Field(default=5004)
    train_agent_port: int = Field(default=5005)

    # ================================================================
    # MCP Server Ports
    # ================================================================
    weather_mcp_port: int = Field(default=5010)
    flight_mcp_port: int = Field(default=5011)
    hotel_mcp_port: int = Field(default=5012)
    db_mcp_port: int = Field(default=5013)
    train_mcp_port: int = Field(default=5014)

    # ================================================================
    # API Gateway & Streamlit
    # ================================================================
    api_gateway_port: int = Field(default=8000)
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
