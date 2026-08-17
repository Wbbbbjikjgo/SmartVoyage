"""Hotel MCP tool server backed by the AMap (高德) POI search API.

数据来源：高德开放平台「关键字搜索」接口
- 接口地址：``/v3/place/text``（keywords=酒店）

说明：高德 POI 返回酒店的名称/地址/评分/电话/图片等信息，但不提供
实时房价，因此房价字段会以区间或近似值呈现，供行程规划参考。
"""

import logging
import random
from typing import Any, Dict, List, Optional

import httpx

from configs.settings import settings
from mcp_servers.base import BaseMCPServer
from mcp_servers.city_codes import city_to_adcode

logger = logging.getLogger(__name__)

_PLACE_ENDPOINT = "/v3/place/text"


class HotelMCPServer(BaseMCPServer):
    """MCP server providing hotel search via AMap POI search."""

    name = "Hotel Tools"
    description = "酒店查询工具集（高德开放平台）"

    def __init__(self, mock_mode: Optional[bool] = None):
        """Initialize the hotel MCP server.

        Args:
            mock_mode: Override mock mode. Defaults to ``settings.hotel_mock_mode``.
        """
        super().__init__(
            mock_mode=settings.hotel_mock_mode if mock_mode is None else mock_mode
        )
        self.api_key = settings.amap_api_key
        self.base_url = settings.amap_base_url.rstrip("/")

    async def search_hotels(
        self,
        location: str,
        check_in: str = "",
        check_out: str = "",
        guests: int = 2,
        price_range: str = None,
        limit: int = 15,
    ) -> Dict[str, Any]:
        """搜索指定城市的酒店。

        Args:
            location: 城市名称（如 "北京"）。
            check_in: 入住日期（YYYY-MM-DD，高德不参与价格计算，仅回显）。
            check_out: 退房日期（同上）。
            guests: 入住人数（回显）。
            price_range: 价格范围（如 "200-500"，仅用于模拟数据）。
            limit: 返回酒店数量上限。

        Returns:
            归一化后的酒店搜索结果。
        """
        if self.mock_mode:
            return _mock_search_hotels(location, check_in, check_out, guests, price_range)

        try:
            data = await self.get_json(
                f"{self.base_url}{_PLACE_ENDPOINT}",
                params={
                    "key": self.api_key,
                    "keywords": "酒店",
                    "city": location,
                    "offset": str(min(max(limit, 1), 25)),
                    "page": "1",
                    "extensions": "all",
                },
            )
        except httpx.HTTPError as exc:
            logger.warning("酒店接口调用失败，降级为模拟数据: %s", exc)
            return _mock_search_hotels(location, check_in, check_out, guests, price_range)

        return self._normalize_hotels(location, check_in, check_out, guests, data)

    async def get_hotel_detail(
        self, hotel_name: str, city: str = "", date: str = ""
    ) -> Dict[str, Any]:
        """获取指定酒店的详细信息。

        Args:
            hotel_name: 酒店名称。
            city: 所在城市（可选，用于缩小搜索范围）。
            date: 入住日期（可选）。

        Returns:
            酒店详情数据。
        """
        if self.mock_mode:
            return _mock_hotel_detail(hotel_name, date)

        try:
            data = await self.get_json(
                f"{self.base_url}{_PLACE_ENDPOINT}",
                params={
                    "key": self.api_key,
                    "keywords": hotel_name,
                    "city": city,
                    "offset": "1",
                    "page": "1",
                    "extensions": "all",
                },
            )
        except httpx.HTTPError as exc:
            logger.warning("酒店详情接口调用失败: %s", exc)
            return self.error(f"酒店详情查询失败: {exc}")

        result = self._normalize_hotels(city, date, date, 1, data)
        hotels = result.get("hotels", [])
        if hotels:
            return hotels[0]
        return self.error(f"未查询到酒店「{hotel_name}」的详情")

    async def search_attractions(self, location: str, limit: int = 10) -> Dict[str, Any]:
        """搜索指定城市的景点（高德 POI，keywords=景点）。

        Args:
            location: 城市名称（如 "北京"）。
            limit: 返回景点数量上限。

        Returns:
            归一化后的景点搜索结果。
        """
        if self.mock_mode:
            return _mock_search_attractions(location, limit)

        try:
            data = await self._search_poi("景点", location, limit)
        except httpx.HTTPError as exc:
            logger.warning("景点接口调用失败，降级为模拟数据: %s", exc)
            return _mock_search_attractions(location, limit)

        pois = data.get("pois") or []
        return {
            "location": location,
            "attractions": [_normalize_attraction_item(p) for p in pois],
            "total": len(pois),
            "source": "amap",
        }

    async def _search_poi(self, keywords: str, city: str, limit: int) -> Dict[str, Any]:
        """调用高德关键字搜索接口，返回原始 POI 响应。"""
        return await self.get_json(
            f"{self.base_url}{_PLACE_ENDPOINT}",
            params={
                "key": self.api_key,
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

    def get_tools(self) -> list:
        """Get list of available tools (MCP schema)."""
        return [
            {
                "name": "search_hotels",
                "description": "搜索可用酒店",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "城市名称"},
                        "check_in": {"type": "string", "description": "入住日期（YYYY-MM-DD）"},
                        "check_out": {"type": "string", "description": "退房日期（YYYY-MM-DD）"},
                        "guests": {"type": "integer", "description": "入住人数", "default": 2},
                    },
                    "required": ["location"],
                },
            },
            {
                "name": "get_hotel_detail",
                "description": "获取酒店详细信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "hotel_name": {"type": "string", "description": "酒店名称"},
                        "city": {"type": "string", "description": "所在城市"},
                    },
                    "required": ["hotel_name"],
                },
            },
        ]


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

    # 高德不提供实时房价，用评分近似生成一个参考价位区间，供演示展示
    estimated_price = _estimate_price(rating)

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
        "price_per_night": estimated_price,
        "currency": "CNY",
        "amenities": _mock_amenities(),
        "source": "amap",
        "note": "高德 POI 不含实时房价，价格为参考估值",
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


def _estimate_price(rating: Optional[float]) -> int:
    """Estimate a reference price band from a hotel rating."""
    base = 300 if rating is None else int(rating * 100)
    return base + random.randint(0, 200)


_AMENITIES_POOL = [
    "免费WiFi", "停车场", "早餐", "健身房", "餐厅", "前台24小时",
    "行李寄存", "接机服务", "商务中心", "洗衣服务",
]


def _mock_amenities() -> List[str]:
    """Return a random subset of amenities for display."""
    return random.sample(_AMENITIES_POOL, random.randint(3, 6))


# ================================================================
# Mock data generators
# ================================================================

def _mock_search_hotels(
    location: str,
    check_in: str,
    check_out: str,
    guests: int,
    price_range: str,
) -> Dict[str, Any]:
    """Generate rich mock hotel search results."""
    chains = ["如家酒店", "汉庭酒店", "全季酒店", "亚朵酒店", "希尔顿酒店", "洲际酒店"]
    num_hotels = random.randint(10, 14)
    hotels = []
    for _ in range(num_hotels):
        rating = round(random.uniform(3.5, 5.0), 1)
        if price_range:
            try:
                low, high = map(int, price_range.split("-"))
                price = random.randint(low, high)
            except ValueError:
                price = random.randint(200, 1200)
        else:
            price = random.randint(200, 1500)
        hotels.append({
            "hotel_name": f"{random.choice(chains)}({location}店)",
            "address": f"{location}市某街道{random.randint(1, 999)}号",
            "district": "市中心",
            "city": location,
            "rating": rating,
            "price_per_night": price,
            "currency": "CNY",
            "amenities": _mock_amenities(),
            "source": "mock",
        })
    hotels.sort(key=lambda x: x["rating"], reverse=True)
    return {
        "location": location,
        "check_in": check_in,
        "check_out": check_out,
        "guests": guests,
        "hotels": hotels,
        "total": len(hotels),
        "source": "mock",
    }


def _mock_hotel_detail(hotel_name: str, date: str) -> Dict[str, Any]:
    """Generate mock hotel detail."""
    return {
        "hotel_name": hotel_name,
        "address": "某街道123号",
        "rating": round(random.uniform(3.5, 5.0), 1),
        "tel": ["010-12345678"],
        "amenities": _mock_amenities(),
        "price_per_night": random.randint(200, 1500),
        "currency": "CNY",
        "date": date,
        "source": "mock",
    }


# 常见城市代表性景点（mock 兜底用）
_MOCK_ATTRACTIONS = [
    "天安门广场", "故宫博物院", "八达岭长城", "颐和园", "天坛公园",
    "南锣鼓巷", "王府井大街", "北海公园", "圆明园", "奥林匹克公园",
    "香山公园", "什刹海", "鸟巢", "水立方", "国子监",
]


def _mock_search_attractions(location: str, limit: int) -> Dict[str, Any]:
    """Generate mock attraction search results."""
    picked = random.sample(_MOCK_ATTRACTIONS, min(limit, len(_MOCK_ATTRACTIONS)))
    attractions = [
        {
            "name": a,
            "address": f"{location}市",
            "district": "市中心",
            "city": location,
            "rating": round(random.uniform(4.0, 5.0), 1),
            "source": "mock",
        }
        for a in picked
    ]
    return {
        "location": location,
        "attractions": attractions,
        "total": len(attractions),
        "source": "mock",
    }


# Global instance
hotel_mcp = HotelMCPServer()
