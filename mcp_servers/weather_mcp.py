"""Weather MCP tool server backed by the AMap (高德) weather API.

数据来源：高德开放平台「天气查询」接口
- 实况天气：``/v3/weather/weatherInfo`` (extensions=base)
- 天气预报：``/v3/weather/weatherInfo`` (extensions=all, 未来最多 4 天)

高德接口要求 ``city`` 为 adcode（行政区划编码），本模块优先使用本地
静态映射（零额外调用），未知城市回退到地理编码接口动态解析。
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import httpx

from configs.settings import settings
from mcp_servers.base import BaseMCPServer
from mcp_servers.city_codes import city_to_adcode

logger = logging.getLogger(__name__)

# 高德天气接口路径
_WEATHER_ENDPOINT = "/v3/weather/weatherInfo"
_GEOCODE_ENDPOINT = "/v3/geocode/geo"


class WeatherMCPServer(BaseMCPServer):
    """MCP server providing real-time and forecast weather via AMap."""

    name = "Weather Tools"
    description = "天气查询工具集（高德开放平台）"

    def __init__(self, mock_mode: Optional[bool] = None):
        """Initialize the weather MCP server.

        Args:
            mock_mode: Override mock mode. Defaults to ``settings.weather_mock_mode``.
        """
        super().__init__(
            mock_mode=settings.weather_mock_mode if mock_mode is None else mock_mode
        )
        self.api_key = settings.amap_api_key
        self.base_url = settings.amap_base_url.rstrip("/")
        self._adcode_cache: Dict[str, str] = {}

    # ================================================================
    # Public tools
    # ================================================================

    async def get_current_weather(self, location: str) -> Dict[str, Any]:
        """获取指定城市的实况天气。

        Args:
            location: 城市名称（如 "北京"）。

        Returns:
            归一化后的实况天气数据，含 ``source`` 字段标识真实/模拟来源。
        """
        try:
            if self.mock_mode:
                return _mock_current_weather(location)

            adcode = await self._resolve_adcode(location)
            if not adcode:
                return self.error(f"未找到城市「{location}」的行政区划编码")

            data = await self.get_json(
                f"{self.base_url}{_WEATHER_ENDPOINT}",
                params={
                    "key": self.api_key,
                    "city": adcode,
                    "extensions": "base",
                    "output": "JSON",
                },
            )
            return self._parse_current_weather(location, adcode, data)

        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("获取实况天气失败，降级为模拟数据: %s", exc)
            return _mock_current_weather(location)

    async def get_forecast(self, location: str, days: int = 3) -> Dict[str, Any]:
        """获取指定城市的天气预报（高德接口最多返回未来 4 天）。

        Args:
            location: 城市名称（如 "北京"）。
            days: 需要的预报天数（1-4）。

        Returns:
            归一化后的天气预报数据。
        """
        try:
            if self.mock_mode:
                return _mock_forecast(location, days)

            adcode = await self._resolve_adcode(location)
            if not adcode:
                return self.error(f"未找到城市「{location}」的行政区划编码")

            data = await self.get_json(
                f"{self.base_url}{_WEATHER_ENDPOINT}",
                params={
                    "key": self.api_key,
                    "city": adcode,
                    "extensions": "all",
                    "output": "JSON",
                },
            )
            return self._parse_forecast(location, adcode, data, days)

        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("获取天气预报失败，降级为模拟数据: %s", exc)
            return _mock_forecast(location, days)

    # ================================================================
    # Internal helpers
    # ================================================================

    async def _resolve_adcode(self, city: str) -> Optional[str]:
        """将城市名解析为高德 adcode（静态映射优先，地理编码兜底）。"""
        normalized = city.strip()
        if normalized in self._adcode_cache:
            return self._adcode_cache[normalized]

        adcode = city_to_adcode(normalized)
        if not adcode:
            try:
                data = await self.get_json(
                    f"{self.base_url}{_GEOCODE_ENDPOINT}",
                    params={"address": normalized, "key": self.api_key},
                )
                geocodes = data.get("geocodes") or []
                if geocodes:
                    adcode = geocodes[0].get("adcode")
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("地理编码接口调用失败: %s", exc)

        if adcode:
            self._adcode_cache[normalized] = adcode
        return adcode

    def _parse_current_weather(
        self, location: str, adcode: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse AMap base weather response into a normalized dict."""
        lives = data.get("lives") or []
        if not lives:
            return self.error(f"未查询到「{location}」的天气数据")
        live = lives[0]
        return {
            "location": live.get("city") or location,
            "adcode": adcode,
            "description": live.get("weather", ""),
            "temperature": _to_float(live.get("temperature")),
            "humidity": _to_float(live.get("humidity")),
            "wind_direction": live.get("winddirection", ""),
            "wind_power": live.get("windpower", ""),
            "report_time": live.get("reporttime", ""),
            "source": "amap",
        }

    def _parse_forecast(
        self, location: str, adcode: str, data: Dict[str, Any], days: int
    ) -> Dict[str, Any]:
        """Parse AMap all weather response into a normalized dict."""
        forecasts = data.get("forecasts") or []
        if not forecasts:
            return self.error(f"未查询到「{location}」的天气预报数据")

        casts = forecasts[0].get("casts") or []
        forecast = []
        for day in casts[: max(1, min(days, len(casts)))]:
            forecast.append({
                "date": day.get("date", ""),
                "week": day.get("week", ""),
                "day_weather": day.get("dayweather", ""),
                "night_weather": day.get("nightweather", ""),
                "day_temp": _to_float(day.get("daytemp")),
                "night_temp": _to_float(day.get("nighttemp")),
                "day_wind": day.get("daywind", ""),
                "night_wind": day.get("nightwind", ""),
                "day_power": day.get("daypower", ""),
                "night_power": day.get("nightpower", ""),
            })
        return {
            "location": forecasts[0].get("city") or location,
            "adcode": adcode,
            "forecast": forecast,
            "report_time": forecasts[0].get("reporttime", ""),
            "source": "amap",
        }

    def get_tools(self) -> list:
        """Get list of available tools (MCP schema)."""
        return [
            {
                "name": "get_current_weather",
                "description": "获取指定城市的实况天气",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "城市名称"},
                    },
                    "required": ["location"],
                },
            },
            {
                "name": "get_forecast",
                "description": "获取指定城市的天气预报（未来最多4天）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "城市名称"},
                        "days": {"type": "integer", "description": "预报天数", "default": 3},
                    },
                    "required": ["location"],
                },
            },
        ]


# ================================================================
# Mock data generators (used when mock mode is on or API fails)
# ================================================================

_CONDITIONS = ["晴", "多云", "阴", "小雨", "中雨", "雷阵雨", "小雪", "雾"]
_WINDS = ["北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风"]


def _to_float(value: Any) -> float:
    """Safely convert a possibly-string numeric value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _mock_current_weather(location: str) -> Dict[str, Any]:
    """Generate deterministic-ish mock current weather."""
    import random

    return {
        "location": location,
        "adcode": city_to_adcode(location) or "",
        "description": random.choice(_CONDITIONS),
        "temperature": round(random.uniform(5, 35), 1),
        "humidity": random.randint(30, 90),
        "wind_direction": random.choice(_WINDS),
        "wind_power": f"{random.randint(1, 6)}级",
        "report_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "mock",
    }


def _mock_forecast(location: str, days: int) -> Dict[str, Any]:
    """Generate mock forecast data."""
    import random

    today = datetime.now().date()
    forecast = []
    for i in range(max(1, min(days, 4))):
        forecast.append({
            "date": (today + timedelta(days=i)).isoformat(),
            "week": str((today + timedelta(days=i)).weekday() + 1),
            "day_weather": random.choice(_CONDITIONS),
            "night_weather": random.choice(_CONDITIONS),
            "day_temp": round(random.uniform(20, 35), 1),
            "night_temp": round(random.uniform(10, 24), 1),
            "day_wind": random.choice(_WINDS),
            "night_wind": random.choice(_WINDS),
            "day_power": f"{random.randint(1, 3)}-{random.randint(3, 5)}",
            "night_power": f"{random.randint(1, 3)}-{random.randint(3, 5)}",
        })
    return {
        "location": location,
        "adcode": city_to_adcode(location) or "",
        "forecast": forecast,
        "report_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "mock",
    }


# Global instance
weather_mcp = WeatherMCPServer()
