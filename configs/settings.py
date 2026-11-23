"""Application settings and configuration management.

所有外部数据均来自真实接口：高德开放平台（天气 / 酒店 / 景点）与阿里云
API 市场（航班 / 火车票）。项目中不再提供任何 mock / 模拟数据开关。
若缺少对应 API Key，工具会明确返回错误，而不是伪造数据。
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ================================================================
    # LLM Configuration (DeepSeek / OpenAI compatible)
    # ================================================================
    openai_api_key: str = Field(default="", description="OpenAI/DeepSeek API key")
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
    amap_api_key: str = Field(default="", description="高德开放平台 Web 服务 API key")
    amap_base_url: str = Field(
        default="https://restapi.amap.com",
        description="高德开放平台 REST API 基础地址",
    )

    # ================================================================
    # Aliyun API Market (阿里云 API 市场) - flight / train
    # ================================================================
    aliyun_appcode: str = Field(default="", description="阿里云 API 市场 AppCode")
    aliyun_flight_url: str = Field(
        default="https://flightss.market.alicloudapi.com/flight/query",
        description="阿里云航班查询接口地址",
    )
    aliyun_train_url: str = Field(
        default="http://jisutrainf.market.alicloudapi.com/train/station2s",
        description="阿里云火车票查询接口地址",
    )

    # ================================================================
    # MySQL Configuration
    # ================================================================
    mysql_host: str = Field(default="localhost")
    mysql_port: int = Field(default=3306)
    mysql_user: str = Field(default="root")
    mysql_password: str = Field(default="", description="MySQL password")
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
    # A2A Agent Network
    # ================================================================
    agent_host: str = Field(
        default="127.0.0.1",
        description="A2A Agent 监听地址（Agent Card 中的 URL 使用该地址）",
    )
    registry_port: int = Field(default=5000, description="Agent 注册中心端口")
    registry_url: str = Field(
        default="http://127.0.0.1:5000",
        description="Agent 注册中心地址",
    )
    registry_heartbeat_interval: int = Field(
        default=30,
        description="Agent 向注册中心发送心跳的间隔（秒）",
    )
    registry_ttl: int = Field(
        default=90,
        description="注册中心中 Agent 的过期时间（秒）",
    )
    a2a_timeout: float = Field(
        default=180.0,
        description="调用远程 A2A Agent 的超时时间（秒）",
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

    @property
    def agent_base_urls(self) -> dict:
        """Static fallback URLs for every A2A agent (used when registry is down)."""
        host = self.agent_host
        return {
            "weather": f"http://{host}:{self.weather_agent_port}",
            "flight": f"http://{host}:{self.flight_agent_port}",
            "hotel": f"http://{host}:{self.hotel_agent_port}",
            "itinerary": f"http://{host}:{self.itinerary_agent_port}",
            "train": f"http://{host}:{self.train_agent_port}",
        }




# Global settings instance
settings = Settings()
