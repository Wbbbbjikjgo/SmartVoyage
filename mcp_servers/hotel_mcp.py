"""Hotel MCP Server (stdio) backed by the real AMap POI search API.

启动方式::

    python -m mcp_servers.hotel_mcp

真实数据来源：高德开放平台「关键字搜索」接口
- 酒店：``/v3/place/text``（keywords=酒店）
- 景点：``/v3/place/text``（keywords=景点）

说明：高德 POI 返回酒店的名称/地址/评分/电话/图片等信息，但 **不提供实时
房价与设施清单**。因此 ``price_per_night`` 与 ``amenities`` 保持为空，绝不
用随机数伪造。本文件不包含任何模拟数据。
"""

import logging
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP

from configs.settings import settings
from mcp_servers.base import BaseMCPServer, configure_stdio_logging, dump

logger = logging.getLogger(__name__)

_PLACE_ENDPOINT = "/v3/place/text"

mcp = FastMCP("smartvoyage_hotel", log_level="ERROR")


class HotelMCPServer(BaseMCPServer):
    """Hotel & attraction tools backed by the real AMap POI search."""

    name = "Hotel Tools"
    description = "酒店/景点查询工具集（高德开放平台真实数据）"

    def __init__(self) -> None:
        super().__init__()
        self.api_key = settings.amap_api_key
        self.base_url = settings.amap_base_url.rstrip("/")

    async def search_hotels(
        self,
        location: str,
        check_in: str = "",
        check_out: str = "",
        guests: int = 2,
        limit: int = 15,
    ) -> Dict[str, Any]:
        """搜索指定城市的真实酒店（高德 POI）。"""
        try:
            key = self.require(self.api_key, "AMAP_API_KEY")
            data = await self._search_poi(key, "酒店", location, limit)
        except (httpx.HTTPError, RuntimeError) as exc:
            logger.warning("酒店接口调用失败: %s", exc)
            return self.error(f"酒店查询失败: {exc}")

        return self._normalize_hotels(location, check_in, check_out, guests, data)

    async def get_hotel_detail(
        self, hotel_name: str, city: str = "", date: str = ""
    ) -> Dict[str, Any]:
        """获取指定酒店的真实详细信息（高德 POI）。"""
        try:
            key = self.require(self.api_key, "AMAP_API_KEY")
            data = await self._search_poi(key, hotel_name, city, 1)
        except (httpx.HTTPError, RuntimeError) as exc:
            logger.warning("酒店详情接口调用失败: %s", exc)
            return self.error(f"酒店详情查询失败: {exc}")

        pois = data.get("pois") or []
        if pois:
            detail = _normalize_hotel_item(pois[0])
            detail["date"] = date
            return detail
        return self.error(f"未查询到酒店「{hotel_name}」的详情")

    async def search_attractions(self, location: str, limit: int = 10) -> Dict[str, Any]:
        """搜索指定城市的真实景点（高德 POI）。"""
        try:
            key = self.require(self.api_key, "AMAP_API_KEY")
            data = await self._search_poi(key, "景点", location, limit)
        except (httpx.HTTPError, RuntimeError) as exc:
            logger.warning("景点接口调用失败: %s", exc)
            return self.error(f"景点查询失败: {exc}")

        pois = data.get("pois") or []
        return {
            "location": location,
            "attractions": [_normalize_attraction_item(p) for p in pois],
            "total": len(pois),
            "source": "amap",
        }

    async def _search_poi(
        self, key: str, keywords: str, city: str, limit: int
    ) -> Dict[str, Any]:
        """调用高德关键字搜索接口，返回原始 POI 响应。"""
        return await self.get_json(
            f"{self.base_url}{_PLACE_ENDPOINT}",
            params={
                "key": key,
                "keywords": keywords,
                "city": city,
                "offset": str(min(max(limit, 1), 25)),
                "page": "1",
                "extensions": "all",
            },
        )

    def _normalize_hotels(
        self,
        location: str,
        check_in: str,
        check_out: str,
        guests: int,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Normalize the AMap POI response into the internal hotel schema."""
        pois = data.get("pois") or []
        hotels = [_normalize_hotel_item(poi) for poi in pois]

        return {
            "location": location,
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "hotels": hotels,
            "total": len(hotels),
            "source": "amap",
        }


# ================================================================
# Normalization helpers
# ================================================================

def _normalize_hotel_item(poi: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single AMap POI into the internal hotel schema."""
    if not isinstance(poi, dict):
        return poi

    biz_ext = poi.get("biz_ext") or {}
    rating = biz_ext.get("rating") or poi.get("rating")
    try:
        rating = float(rating) if rating else None
    except (TypeError, ValueError):
        rating = None

    photos = [p.get("url") for p in (poi.get("photos") or []) if isinstance(p, dict) and p.get("url")]

    return {
        "hotel_name": poi.get("name", ""),
        "address": poi.get("address", ""),
        "district": poi.get("adname", ""),
        "city": poi.get("cityname", ""),
        "location": _readable_location(poi),
        "coords": _format_location(poi),
        "rating": rating,
        "tel": _split_tels(poi.get("tel")),
        "photos": photos,
        # 高德 POI 不提供实时房价与设施，保持为空而不是伪造
        "price_per_night": None,
        "currency": "CNY",
        "amenities": [],
        "source": "amap",
        "note": "高德 POI 不提供实时房价与设施信息",
    }


def _readable_location(poi: Dict[str, Any]) -> str:
    """Compose a human-readable location string from city + district."""
    parts = [poi.get("cityname", ""), poi.get("adname", "")]
    return "".join(p for p in parts if p)


def _normalize_attraction_item(poi: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single AMap POI into the attraction schema."""
    if not isinstance(poi, dict):
        return poi

    biz_ext = poi.get("biz_ext") or {}
    rating = biz_ext.get("rating") or poi.get("rating")
    try:
        rating = float(rating) if rating else None
    except (TypeError, ValueError):
        rating = None

    photos = [p.get("url") for p in (poi.get("photos") or []) if isinstance(p, dict) and p.get("url")]

    return {
        "name": poi.get("name", ""),
        "address": poi.get("address", ""),
        "district": poi.get("adname", ""),
        "city": poi.get("cityname", ""),
        "location": _readable_location(poi),
        "coords": _format_location(poi),
        "rating": rating,
        "photos": photos,
        "source": "amap",
    }


def _format_location(poi: Dict[str, Any]) -> str:
    """Format POI coordinates as 'lng,lat'."""
    loc = poi.get("location")
    if isinstance(loc, str) and loc:
        return loc
    if isinstance(loc, (list, tuple)) and len(loc) == 2:
        return f"{loc[0]},{loc[1]}"
    return ""


def _split_tels(tel: Any) -> List[str]:
    """Split a semicolon-joined telephone string into a list."""
    if not tel:
        return []
    if isinstance(tel, str):
        return [t.strip() for t in tel.split(";") if t.strip()]
    if isinstance(tel, list):
        return [str(t) for t in tel]
    return [str(tel)]


hotel_server = HotelMCPServer()


# ================================================================
# MCP Tools
# ================================================================

@mcp.tool()
async def search_hotels(
    location: str,
    check_in: str = "",
    check_out: str = "",
    guests: int = 2,
    limit: int = 15,
) -> str:
    """搜索指定城市的真实酒店（高德 POI，含评分/地址/电话）。

    Args:
        location: 城市名称，例如「北京」。
        check_in: 入住日期（YYYY-MM-DD，仅回显）。
        check_out: 退房日期（YYYY-MM-DD，仅回显）。
        guests: 入住人数。
        limit: 返回数量上限（1-25）。
    """
    return dump(
        await hotel_server.search_hotels(
            location, check_in, check_out, guests, limit
        )
    )


@mcp.tool()
async def get_hotel_detail(
    hotel_name: str, city: str = "", date: str = ""
) -> str:
    """获取指定酒店的真实详细信息（高德 POI）。

    Args:
        hotel_name: 酒店名称。
        city: 所在城市（可选）。
        date: 入住日期（可选）。
    """
    return dump(await hotel_server.get_hotel_detail(hotel_name, city, date))


@mcp.tool()
async def search_attractions(location: str, limit: int = 10) -> str:
    """搜索指定城市的真实景点（高德 POI，用于旅游规划）。

    Args:
        location: 城市名称，例如「北京」。
        limit: 返回景点数量上限（1-25）。
    """
    return dump(await hotel_server.search_attractions(location, limit))


if __name__ == "__main__":
    configure_stdio_logging()
    mcp.run(transport="stdio")
