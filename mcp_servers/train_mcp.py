"""Train MCP Server (stdio) backed by the real Aliyun API Market.

启动方式::

    python -m mcp_servers.train_mcp

数据来源：阿里云 API 市场「全国火车票查询（极速数据）」
- 接口地址：``http://jisutrainf.market.alicloudapi.com/train/station2s``
- 鉴权方式：请求头 ``Authorization: APPCODE <appcode>``

本文件不包含任何模拟数据：缺少 AppCode 或接口失败时返回明确错误。
"""

import logging
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP

from configs.settings import settings
from mcp_servers.base import BaseMCPServer, configure_stdio_logging, dump

logger = logging.getLogger(__name__)

mcp = FastMCP("smartvoyage_train", log_level="ERROR")


class TrainMCPServer(BaseMCPServer):
    """Train tools backed by the real Aliyun API Market."""

    name = "Train Tools"
    description = "高铁/火车票查询工具集（阿里云 API 市场真实数据）"

    def __init__(self) -> None:
        super().__init__()
        self.appcode = settings.aliyun_appcode
        self.base_url = settings.aliyun_train_url.rstrip("/")

    async def search_trains(
        self,
        start: str,
        end: str,
        date: str = "",
        is_high_speed: int = 0,
    ) -> Dict[str, Any]:
        """搜索指定出发/到达站点在指定日期的真实火车票。"""
        if not start or not end:
            return self.error("出发站和到达站不能为空")

        try:
            appcode = self.require(self.appcode, "ALIYUN_APPCODE")
        except RuntimeError as exc:
            return self.error(str(exc))

        params: Dict[str, Any] = {
            "start": start,
            "end": end,
            "ishigh": int(is_high_speed),
        }
        if date:
            params["date"] = date

        try:
            data = await self.get_json(
                self.base_url,
                params=params,
                headers={"Authorization": f"APPCODE {appcode}"},
            )
        except (httpx.HTTPError, RuntimeError) as exc:
            logger.warning("火车票接口调用失败: %s", exc)
            return self.error(f"火车票接口调用失败: {exc}")

        return self._normalize_trains(start, end, date, data)

    def _normalize_trains(
        self, start: str, end: str, date: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normalize the vendor response into the internal train schema."""
        items = _extract_list(data)
        trains = [_normalize_train_item(item, start, end) for item in items]

        return {
            "departure": start,
            "arrival": end,
            "date": date,
            "trains": trains,
            "total": len(trains),
            "source": "aliyun",
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
    """Best-effort extraction of the train list from a vendor response."""
    if not isinstance(data, dict):
        return []

    result = data.get("result")
    if isinstance(result, dict):
        result = result.get("list") or result.get("trains") or result.get("data")
    if isinstance(result, list):
        return result

    for key in ("data", "list", "trains"):
        candidate = data.get(key)
        if isinstance(candidate, list):
            return candidate
    return []


def _normalize_train_item(
    item: Dict[str, Any], start: str, end: str
) -> Dict[str, Any]:
    """Normalize a single train item into the internal schema.

    实测极速数据接口字段：trainno/type/typename/station/endstation/
    departuretime/arrivaltime/costtime/day + 各席别 price 字段。
    """
    if not isinstance(item, dict):
        return item

    train_no = str(_pick(item, "trainno", "trainNo", "train_no", "checi", "trainCode") or "")
    seats = _extract_seats(item)
    return {
        "train_no": train_no,
        "train_type": _pick(item, "typename", "trainType", "train_type", "typeName")
        or _infer_type(train_no),
        "departure": start,
        "arrival": end,
        "departure_station": _pick(item, "station", "startStation", "fromStation", "from", "start_station"),
        "arrival_station": _pick(item, "endstation", "endStation", "toStation", "to", "end_station"),
        "departure_time": _pick(item, "departuretime", "startTime", "fromTime", "departureTime", "start_time"),
        "arrival_time": _pick(item, "arrivaltime", "endTime", "toTime", "arrivalTime", "end_time"),
        "duration": _pick(item, "costtime", "runTime", "duration", "costTime", "travelTime"),
        "day": _pick(item, "day"),
        "seats": seats,
        "price": _default_price(seats),
        "date": _pick(item, "date", "trainDate"),
    }


# 12306 席别缩写 → 中文名称（极速数据接口的 price 字段命名规则）
_SEAT_PRICE_FIELDS = {
    "商务座": ("pricesw",),
    "特等座": ("pricetd", "pricetdz"),
    "一等座": ("priceyd", "priceydz"),
    "二等座": ("priceed", "priceedz"),
    "高级软卧": ("pricegr",),
    "动卧": ("pricedw",),
    "软卧": ("pricerw", "pricerw2"),
    "硬卧": ("priceyw", "priceyw3"),
    "硬座": ("priceyz",),
    "软座": ("pricerz",),
    "无座": ("pricewz",),
}


def _extract_seats(item: Dict[str, Any]) -> Dict[str, float]:
    """Extract seat price map from a train item (12306 席别缩写)。"""
    seats: Dict[str, float] = {}
    for label, fields in _SEAT_PRICE_FIELDS.items():
        for field in fields:
            value = item.get(field)
            if value in (None, "", "-"):
                continue
            try:
                seats[label] = float(value)
            except (TypeError, ValueError):
                pass
            break
    return seats


def _default_price(seats: Dict[str, float]) -> Optional[float]:
    """Return a representative price (prefer 二等座 then 无座 then first seat)."""
    for label in ("二等座", "无座"):
        if label in seats:
            return seats[label]
    if seats:
        return next(iter(seats.values()))
    return None


def _infer_type(train_no: str) -> str:
    """Infer train type from its number prefix."""
    if not train_no:
        return ""
    prefix = train_no[0].upper()
    if prefix == "G":
        return "高铁"
    if prefix == "D":
        return "动车"
    if prefix == "C":
        return "城际"
    if prefix in ("K", "T", "Z"):
        return "普速"
    return "其他"


train_server = TrainMCPServer()


# ================================================================
# MCP Tools
# ================================================================

@mcp.tool()
async def search_trains(
    start: str,
    end: str,
    date: str = "",
    is_high_speed: int = 0,
) -> str:
    """搜索指定出发/到达站点的真实高铁/火车票（阿里云 API 市场）。

    Args:
        start: 出发城市或车站，例如「杭州」。
        end: 到达城市或车站，例如「北京」。
        date: 出行日期（YYYY-MM-DD，可选）。
        is_high_speed: 是否仅查高铁（1 是，0 不限）。
    """
    return dump(
        await train_server.search_trains(start, end, date, is_high_speed)
    )


if __name__ == "__main__":
    configure_stdio_logging()
    mcp.run(transport="stdio")
