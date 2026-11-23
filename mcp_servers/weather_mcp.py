"""Weather MCP Server (stdio) backed by the real AMap weather API.

启动方式（由 MCP Client 以子进程方式拉起）::

    python -m mcp_servers.weather_mcp

真实数据来源：高德开放平台「天气查询」接口
- 实况天气：``/v3/weather/weatherInfo`` (extensions=base)
- 天气预报：``/v3/weather/weatherInfo`` (extensions=all, 未来最多 4 天)

高德接口要求 ``city`` 为 adcode（行政区划编码），本模块优先使用本地
静态映射，未知城市回退到地理编码接口动态解析。本文件中没有任何模拟数据。
"""

import logging
from typing import Any, Dict, Optional

import httpx
from mcp.server.fastmcp import FastMCP

from configs.settings import settings
from mcp_servers.base import BaseMCPServer, configure_stdio_logging, dump

logger = logging.getLogger(__name__)

# 高德天气接口路径
_WEATHER_ENDPOINT = "/v3/weather/weatherInfo"
_GEOCODE_ENDPOINT = "/v3/geocode/geo"

# 真正的 MCP Server 实例
mcp = FastMCP("smartvoyage_weather", log_level="ERROR")


class WeatherMCPServer(BaseMCPServer):
    """Weather tools backed by the real AMap open platform."""

    name = "Weather Tools"
    description = "天气查询工具集（高德开放平台真实数据）"

    def __init__(self) -> None:
        super().__init__()
        self.api_key = settings.amap_api_key
        self.base_url = settings.amap_base_url.rstrip("/")
        self._adcode_cache: Dict[str, str] = {}

    async def get_current_weather(self, location: str) -> Dict[str, Any]:
        """获取指定城市的实况天气（真实数据）。"""
        try:
            key = self.require(self.api_key, "AMAP_API_KEY")
            adcode = await self._resolve_adcode(location, key)
            if not adcode:
                return self.error(f"未找到城市「{location}」的行政区划编码")

            data = await self.get_json(
                f"{self.base_url}{_WEATHER_ENDPOINT}",
                params={
                    "key": key,
                    "city": adcode,
                    "extensions": "base",
                    "output": "JSON",
                },
            )
            return self._parse_current_weather(location, adcode, data)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            logger.warning("查询实况天气失败: %s", exc)
            return self.error(f"查询实况天气失败: {exc}")

    async def get_forecast(self, location: str, days: int = 3) -> Dict[str, Any]:
        """获取指定城市的天气预报（高德接口最多返回未来 4 天）。"""
        try:
            key = self.require(self.api_key, "AMAP_API_KEY")
            adcode = await self._resolve_adcode(location, key)
            if not adcode:
                return self.error(f"未找到城市「{location}」的行政区划编码")

            data = await self.get_json(
                f"{self.base_url}{_WEATHER_ENDPOINT}",
                params={
                    "key": key,
                    "city": adcode,
                    "extensions": "all",
                    "output": "JSON",
                },
            )
            return self._parse_forecast(location, adcode, data, days)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            logger.warning("查询天气预报失败: %s", exc)
            return self.error(f"查询天气预报失败: {exc}")

    async def _resolve_adcode(self, city: str, key: str) -> Optional[str]:
        """将城市名解析为高德 adcode（静态映射优先，地理编码兜底）。"""
        normalized = city.strip()
        if normalized in self._adcode_cache:
            return self._adcode_cache[normalized]

        from mcp_servers.city_codes import city_to_adcode

        adcode = city_to_adcode(normalized)
        if not adcode:
            data = await self.get_json(
                f"{self.base_url}{_GEOCODE_ENDPOINT}",
                params={"address": normalized, "key": key},
            )
            geocodes = data.get("geocodes") or []
            if geocodes:
                adcode = geocodes[0].get("adcode")

        if adcode:
            self._adcode_cache[normalized] = str(adcode)
        return str(adcode) if adcode else None

    def _parse_current_weather(
        self, location: str, adcode: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse the AMap base weather response into a normalized dict."""
        lives = data.get("lives") or []
        if not lives:
            return self.error(
                f"未查询到「{location}」的天气数据（高德返回: {data.get('info')}）"
            )
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
        """Parse the AMap all-weather response into a normalized dict."""
        forecasts = data.get("forecasts") or []
        if not forecasts:
            return self.error(
                f"未查询到「{location}」的天气预报数据（高德返回: {data.get('info')}）"
            )

        casts = forecasts[0].get("casts") or []
        # 高德最多返回 4 天，绝不凭空扩展天数
        limit = max(1, min(int(days or len(casts)), len(casts)))
        forecast = []
        for day in casts[:limit]:
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


def _to_float(value: Any) -> float:
    """Safely convert a possibly-string numeric value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


weather_server = WeatherMCPServer()


# ================================================================
# MCP Tools（真正注册到 MCP 协议，由 Client 动态发现）
# ================================================================

@mcp.tool()
async def get_current_weather(location: str) -> str:
    """获取指定城市的实况天气（真实数据来自高德开放平台）。

    Args:
        location: 城市名称，例如「北京」「上海」。
    """
    return dump(await weather_server.get_current_weather(location))


@mcp.tool()
async def get_forecast(location: str, days: int = 3) -> str:
    """获取指定城市的天气预报（真实数据，高德最多返回未来 4 天）。

    Args:
        location: 城市名称，例如「北京」「上海」。
        days: 需要的预报天数（1-4）。
    """
    return dump(await weather_server.get_forecast(location, days))


if __name__ == "__main__":
    configure_stdio_logging()
    mcp.run(transport="stdio")
