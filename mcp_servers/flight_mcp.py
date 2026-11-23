"""Flight MCP Server (stdio) backed by the real Aliyun API Market.

启动方式::

    python -m mcp_servers.flight_mcp

数据来源：阿里云 API 市场「全球飞机航班机票信息查询」
- 接口地址：``https://flightss.market.alicloudapi.com/flight/query``
- 鉴权方式：请求头 ``Authorization: APPCODE <appcode>``
- 出发/到达参数为 IATA 城市码或机场码（如 BJS / SHA / CAN）

本文件不包含任何模拟数据：缺少 AppCode、城市不支持或接口失败时，都会
返回明确的错误信息。
"""

import logging
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP

from configs.settings import settings
from mcp_servers.base import BaseMCPServer, configure_stdio_logging, dump
from mcp_servers.city_codes import city_to_iata

logger = logging.getLogger(__name__)

# 航司代码 -> 名称（仅用于上游只返回代码时补全名称，不是伪造航班）
_AIRLINES = {
    "CA": "中国国际航空", "MU": "中国东方航空", "CZ": "中国南方航空",
    "HU": "海南航空", "3U": "四川航空", "ZH": "深圳航空", "MF": "厦门航空",
    "SC": "山东航空", "9C": "春秋航空", "GS": "天津航空", "KN": "中国联合航空",
    "QW": "青岛航空", "DR": "瑞丽航空", "8L": "祥鹏航空",
}

mcp = FastMCP("smartvoyage_flight", log_level="ERROR")


class FlightMCPServer(BaseMCPServer):
    """Flight tools backed by the real Aliyun API Market."""

    name = "Flight Tools"
    description = "航班查询工具集（阿里云 API 市场真实数据）"

    def __init__(self) -> None:
        super().__init__()
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
        """搜索指定航线在指定日期的真实航班。"""
        try:
            appcode = self.require(self.appcode, "ALIYUN_APPCODE")
        except RuntimeError as exc:
            return self.error(str(exc))

        dep_code = city_to_iata(departure)
        arr_code = city_to_iata(arrival)
        if not dep_code or not arr_code:
            missing = departure if not dep_code else arrival
            return self.error(f"暂不支持城市「{missing}」的航班查询")

        params: Dict[str, Any] = {
            "departure": dep_code,
            "arrival": arr_code,
            "departureDate": date,
        }
        if max_segments is not None:
            params["maxSegments"] = str(max_segments)

        try:
            data = await self.get_json(
                self.base_url,
                params=params,
                headers={"Authorization": f"APPCODE {appcode}"},
            )
        except (httpx.HTTPError, RuntimeError) as exc:
            logger.warning("航班接口调用失败: %s", exc)
            return self.error(f"航班接口调用失败: {exc}")

        return self._normalize_flights(departure, arrival, date, passengers, data)

    async def get_flight_detail(
        self, flight_no: str, date: str, departure: str = "", arrival: str = ""
    ) -> Dict[str, Any]:
        """获取指定航班的真实详细信息。"""
        try:
            appcode = self.require(self.appcode, "ALIYUN_APPCODE")
        except RuntimeError as exc:
            return self.error(str(exc))

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
                self.base_url,
                params=params,
                headers={"Authorization": f"APPCODE {appcode}"},
            )
        except (httpx.HTTPError, RuntimeError) as exc:
            logger.warning("航班详情接口调用失败: %s", exc)
            return self.error(f"航班详情查询失败: {exc}")

        result = self._normalize_flights(departure, arrival, date, 1, data)
        flights = result.get("flights", [])
        if flights:
            return flights[0]
        return self.error(f"未查询到航班「{flight_no}」的详情")

    def _normalize_flights(
        self,
        departure: str,
        arrival: str,
        date: str,
        passengers: int,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Normalize the vendor response into the internal flight schema."""
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
    """Best-effort extraction of the flight list from a vendor response.

    实测聚合数据航班接口的返回结构为：``{"reason": "...", "result":
    {"orderid": "...", "flightInfo": [...]}, "error_code": 0}``。
    """
    if not isinstance(data, dict):
        return []

    result = data.get("result")
    if isinstance(result, dict):
        result = (
            result.get("flightInfo")
            or result.get("list")
            or result.get("flights")
            or result.get("data")
        )
    if isinstance(result, list):
        return result

    for key in ("flightInfo", "data", "list", "flights"):
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

    airline_code = str(_pick(item, "airline") or "")
    flight_no = str(_pick(item, "flightNo", "flight_no", "no", "fnum", "flight") or "")
    airline = (
        _pick(item, "airlineName", "airline_name", "airName", "carrier")
        or _AIRLINES.get(airline_code.upper(), airline_code)
    )

    # transferNum 表示航段数（1=直飞，2=一次中转），经停次数 = 航段数 - 1
    segments = _pick(item, "transferNum", "stopCount", "transferCount")
    stops = None
    if segments is not None:
        try:
            stops = max(0, int(segments) - 1)
        except (TypeError, ValueError):
            stops = None

    return {
        "flight_no": flight_no,
        "airline": airline,
        "airline_code": airline_code,
        "is_code_share": _pick(item, "isCodeShare", "codeShare"),
        # 城市名来自调用入参，接口返回的 departure/arrival 为机场码
        "departure": departure,
        "arrival": arrival,
        "departure_airport": _pick(item, "departure", "depAirport", "departureAirport", "fromAirport"),
        "departure_airport_name": _pick(item, "departureName", "departureAirportName"),
        "arrival_airport": _pick(item, "arrival", "arrAirport", "arrivalAirport", "toAirport"),
        "arrival_airport_name": _pick(item, "arrivalName", "arrivalAirportName"),
        "departure_date": _pick(item, "departureDate", "depDate"),
        "departure_time": _pick(item, "departureTime", "depTime", "startTime", "takeoffTime"),
        "arrival_date": _pick(item, "arrivalDate", "arrDate"),
        "arrival_time": _pick(item, "arrivalTime", "arrTime", "endTime", "landTime"),
        "duration": _pick(item, "duration", "flightTime", "elapsedTime", "costTime"),
        "aircraft": _pick(item, "equipment", "aircraft", "planeType", "aircraftType", "craftType"),
        "segments": segments,
        "stops": stops,
        "price": _pick(item, "ticketPrice", "price", "lowestPrice", "minPrice", "adultPrice"),
        "currency": _pick(item, "currency", "currencyCode") or "CNY",
        "available_seats": _pick(item, "availableSeats", "seatCount", "seats", "inventory"),
        "discount": _pick(item, "discount", "discountInfo", "rate"),
        "on_time_rate": _pick(item, "onTimeRate", "punctualityRate", "ontimeRate"),
        "meal": _pick(item, "meal", "mealInfo", "mealService"),
    }


flight_server = FlightMCPServer()


# ================================================================
# MCP Tools
# ================================================================

@mcp.tool()
async def search_flights(
    departure: str,
    arrival: str,
    date: str,
    passengers: int = 1,
    max_segments: Optional[int] = None,
) -> str:
    """搜索指定航线在指定日期的真实航班（阿里云 API 市场）。

    Args:
        departure: 出发城市，例如「北京」。
        arrival: 到达城市，例如「上海」。
        date: 出行日期（YYYY-MM-DD）。
        passengers: 乘客人数。
        max_segments: 最大航段数（可选）。
    """
    return dump(
        await flight_server.search_flights(
            departure, arrival, date, passengers, max_segments
        )
    )


@mcp.tool()
async def get_flight_detail(
    flight_no: str, date: str, departure: str = "", arrival: str = ""
) -> str:
    """获取指定航班的真实详细信息。

    Args:
        flight_no: 航班号，例如「MU8218」。
        date: 航班日期（YYYY-MM-DD）。
        departure: 出发城市（可选）。
        arrival: 到达城市（可选）。
    """
    return dump(
        await flight_server.get_flight_detail(
            flight_no, date, departure, arrival
        )
    )


if __name__ == "__main__":
    configure_stdio_logging()
    mcp.run(transport="stdio")
