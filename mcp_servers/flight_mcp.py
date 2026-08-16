"""Flight MCP tool server backed by Aliyun API Market (聚合数据).

数据来源：阿里云 API 市场「全球飞机航班机票信息查询」
- 接口地址：``https://flightss.market.alicloudapi.com/flight/query``
- 鉴权方式：请求头 ``Authorization: APPCODE <appcode>``
- 出发/到达参数为 IATA 城市码或机场码（如 BJS / SHA / CAN）

注意：该接口为付费接口，免费额度极少（默认仅 3 次），因此默认开启
``mock_mode`` 保护额度。确认配额充足后，将 ``FLIGHT_MOCK_MODE`` 设为
``false`` 即可切换到真实数据。
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from configs.settings import settings
from mcp_servers.base import BaseMCPServer
from mcp_servers.city_codes import city_to_iata

logger = logging.getLogger(__name__)

# 航司代码 -> 名称（用于模拟数据及回显）
_AIRLINES = {
    "CA": "中国国际航空", "MU": "中国东方航空", "CZ": "中国南方航空",
    "HU": "海南航空", "3U": "四川航空", "ZH": "深圳航空", "MF": "厦门航空",
    "SC": "山东航空", "9C": "春秋航空", "GS": "天津航空", "KN": "中国联合航空",
    "QW": "青岛航空", "DR": "瑞丽航空", "8L": "祥鹏航空",
}

_AIRCRAFT = [
    "Boeing 737-800", "Boeing 737 MAX 8", "Boeing 787-9", "Airbus A320",
    "Airbus A321neo", "Airbus A330-300", "Airbus A350-900", "COMAC C919",
    "COMAC ARJ21",
]


class FlightMCPServer(BaseMCPServer):
    """MCP server providing flight search via Aliyun API Market."""

    name = "Flight Tools"
    description = "航班查询工具集（阿里云 API 市场）"

    def __init__(self, mock_mode: Optional[bool] = None):
        """Initialize the flight MCP server.

        Args:
            mock_mode: Override mock mode. Defaults to ``settings.flight_mock_mode``.
        """
        super().__init__(
            mock_mode=settings.flight_mock_mode if mock_mode is None else mock_mode
        )
        self.appcode = settings.aliyun_appcode
        self.base_url = settings.aliyun_flight_url.rstrip("/")

    def _auth_headers(self) -> Dict[str, str]:
        """Build Authorization headers required by Aliyun API Market."""
        return {"Authorization": f"APPCODE {self.appcode}"}

    async def search_flights(
        self,
        departure: str,
        arrival: str,
        date: str,
        passengers: int = 1,
        max_segments: Optional[int] = None,
    ) -> Dict[str, Any]:
        """搜索指定航线在指定日期的航班。

        Args:
            departure: 出发城市（如 "北京"）。
            arrival: 到达城市（如 "上海"）。
            date: 出行日期（YYYY-MM-DD）。
            passengers: 乘客人数（仅回显，不参与上游查询）。
            max_segments: 最大航段数（None 表示不限）。

        Returns:
            归一化后的航班搜索结果。
        """
        dep_code = city_to_iata(departure)
        arr_code = city_to_iata(arrival)

        if not dep_code or not arr_code:
            missing = departure if not dep_code else arrival
            return self.error(f"暂不支持城市「{missing}」的航班查询")

        if self.mock_mode:
            return _mock_search_flights(departure, arrival, date, passengers)

        params: Dict[str, Any] = {
            "departure": dep_code,
            "arrival": arr_code,
            "departureDate": date,
        }
        if max_segments is not None:
            params["maxSegments"] = str(max_segments)

        try:
            data = await self.get_json(
                self.base_url, params=params, headers=self._auth_headers()
            )
        except httpx.HTTPError as exc:
            logger.warning("航班接口调用失败，降级为模拟数据: %s", exc)
            return _mock_search_flights(departure, arrival, date, passengers)

        return self._normalize_flights(departure, arrival, date, passengers, data)

    async def get_flight_detail(
        self, flight_no: str, date: str, departure: str = "", arrival: str = ""
    ) -> Dict[str, Any]:
        """获取指定航班的详细信息。

        Args:
            flight_no: 航班号（如 "MU8218"）。
            date: 航班日期（YYYY-MM-DD）。
            departure: 出发城市（可选，用于缩小范围）。
            arrival: 到达城市（可选）。

        Returns:
            航班详情数据。
        """
        if self.mock_mode:
            return _mock_flight_detail(flight_no, date)

        params: Dict[str, Any] = {"flightNo": flight_no, "departureDate": date}
        if departure:
            dep_code = city_to_iata(departure)
            if dep_code:
                params["departure"] = dep_code
        if arrival:
            arr_code = city_to_iata(arrival)
            if arr_code:
                params["arrival"] = arr_code

        try:
            data = await self.get_json(
                self.base_url, params=params, headers=self._auth_headers()
            )
        except httpx.HTTPError as exc:
            logger.warning("航班详情接口调用失败: %s", exc)
            return self.error(f"航班详情查询失败: {exc}")

        result = self._normalize_flights(departure, arrival, date, 1, data)
        flights = result.get("flights", [])
        if flights:
            return flights[0]
        return self.error(f"未查询到航班「{flight_no}」的详情")

    # ================================================================
    # Response normalization (best-effort across vendor schemas)
    # ================================================================

    def _normalize_flights(
        self,
        departure: str,
        arrival: str,
        date: str,
        passengers: int,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Normalize the vendor response into the internal flight schema.

        The upstream schema may vary; we defensively probe several common
        field names and preserve the raw payload for debugging.
        """
        items = _extract_list(data)
        flights = [_normalize_flight_item(item, departure, arrival) for item in items]

        return {
            "departure": departure,
            "arrival": arrival,
            "date": date,
            "passengers": passengers,
            "flights": flights,
            "total": len(flights),
            "source": "aliyun",
            # 保留原始响应，便于核对字段映射
            "raw": data,
        }

    def get_tools(self) -> list:
        """Get list of available tools (MCP schema)."""
        return [
            {
                "name": "search_flights",
                "description": "搜索可用航班",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "departure": {"type": "string", "description": "出发城市"},
                        "arrival": {"type": "string", "description": "到达城市"},
                        "date": {"type": "string", "description": "出行日期（YYYY-MM-DD）"},
                        "passengers": {"type": "integer", "description": "乘客人数", "default": 1},
                        "max_segments": {"type": "integer", "description": "最大航段数"},
                    },
                    "required": ["departure", "arrival", "date"],
                },
            },
            {
                "name": "get_flight_detail",
                "description": "获取航班详细信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "flight_no": {"type": "string", "description": "航班号"},
                        "date": {"type": "string", "description": "航班日期"},
                    },
                    "required": ["flight_no", "date"],
                },
            },
        ]


# ================================================================
# Normalization helpers
# ================================================================

def _pick(item: Dict[str, Any], *keys: str) -> Any:
    """Return the first non-empty value among candidate keys."""
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _extract_list(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Best-effort extraction of the flight list from a vendor response."""
    if not isinstance(data, dict):
        return []

    result = data.get("result")
    if isinstance(result, dict):
        result = result.get("list") or result.get("flights") or result.get("data")
    if isinstance(result, list):
        return result

    for key in ("data", "list", "flights"):
        candidate = data.get(key)
        if isinstance(candidate, list):
            return candidate
    return []


def _normalize_flight_item(
    item: Dict[str, Any], departure: str, arrival: str
) -> Dict[str, Any]:
    """Normalize a single flight item into the internal schema."""
    if not isinstance(item, dict):
        return item

    flight_no = str(_pick(item, "flightNo", "flight_no", "no", "fnum", "flight") or "")
    airline_code = flight_no[:2] if flight_no else ""
    airline = (
        _pick(item, "airlineName", "airline_name", "airline", "airName", "carrier")
        or _AIRLINES.get(airline_code.upper(), "")
    )

    return {
        "flight_no": flight_no,
        "airline": airline,
        "airline_code": airline_code,
        "departure": _pick(item, "departureCity", "depCity", "fromCity", "departure") or departure,
        "arrival": _pick(item, "arrivalCity", "arrCity", "toCity", "arrival") or arrival,
        "departure_airport": _pick(item, "depAirport", "departureAirport", "fromAirport", "depAirportCode"),
        "arrival_airport": _pick(item, "arrAirport", "arrivalAirport", "toAirport", "arrAirportCode"),
        "departure_time": _pick(item, "departureTime", "depTime", "startTime", "takeoffTime"),
        "arrival_time": _pick(item, "arrivalTime", "arrTime", "endTime", "landTime"),
        "duration": _pick(item, "duration", "flightTime", "elapsedTime", "costTime"),
        "aircraft": _pick(item, "aircraft", "planeType", "aircraftType", "craftType"),
        "stops": _pick(item, "stops", "stopCount", "transferCount", "segments"),
        "price": _pick(item, "price", "ticketPrice", "lowestPrice", "minPrice", "adultPrice"),
        "currency": _pick(item, "currency", "currencyCode") or "CNY",
        "available_seats": _pick(item, "availableSeats", "seatCount", "seats", "inventory"),
        "discount": _pick(item, "discount", "discountInfo", "rate"),
        "on_time_rate": _pick(item, "onTimeRate", "punctualityRate", "ontimeRate"),
        "meal": _pick(item, "meal", "mealInfo", "mealService"),
    }


# ================================================================
# Mock data generators
# ================================================================

def _mock_search_flights(
    departure: str, arrival: str, date: str, passengers: int
) -> Dict[str, Any]:
    """Generate rich mock flight search results."""
    num_flights = random.randint(10, 14)
    flights = []
    for _ in range(num_flights):
        airline_code = random.choice(list(_AIRLINES.keys()))
        dep_hour = random.randint(6, 22)
        dep_minute = random.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55])
        duration_minutes = random.randint(60, 240)
        total_dep = dep_hour * 60 + dep_minute
        total_arr = total_dep + duration_minutes
        flights.append({
            "flight_no": f"{airline_code}{random.randint(1000, 9999)}",
            "airline": _AIRLINES[airline_code],
            "airline_code": airline_code,
            "departure": departure,
            "arrival": arrival,
            "departure_airport": _mock_airport_code(departure),
            "arrival_airport": _mock_airport_code(arrival),
            "departure_time": f"{dep_hour:02d}:{dep_minute:02d}",
            "arrival_time": f"{total_arr // 60 % 24:02d}:{total_arr % 60:02d}",
            "duration": f"{duration_minutes // 60}h {duration_minutes % 60}m",
            "aircraft": random.choice(_AIRCRAFT),
            "stops": 0,
            "price": random.randint(4, 32) * 100,
            "currency": "CNY",
            "available_seats": random.randint(3, 200),
            "discount": f"{random.randint(3, 9)}.{random.randint(0, 9)}折",
            "on_time_rate": f"{random.randint(70, 98)}%",
            "meal": random.choice(["有餐食", "无餐食", "轻食"]),
            "date": date,
        })
    flights.sort(key=lambda x: x["departure_time"])
    return {
        "departure": departure,
        "arrival": arrival,
        "date": date,
        "passengers": passengers,
        "flights": flights,
        "total": len(flights),
        "source": "mock",
    }


def _mock_flight_detail(flight_no: str, date: str) -> Dict[str, Any]:
    """Generate mock flight detail."""
    airline_code = flight_no[:2].upper()
    return {
        "flight_no": flight_no,
        "airline": _AIRLINES.get(airline_code, airline_code),
        "airline_code": airline_code,
        "aircraft": random.choice(_AIRCRAFT),
        "departure_time": "08:30",
        "arrival_time": "10:45",
        "duration": "2h 15m",
        "stops": 0,
        "meal": "有餐食",
        "on_time_rate": "85%",
        "date": date,
        "source": "mock",
    }


def _mock_airport_code(city: str) -> str:
    """Return a plausible airport code for mock data."""
    return city_to_iata(city) or "XXX"


# Global instance
flight_mcp = FlightMCPServer()
