"""Train (高铁/火车票) MCP tool server backed by Aliyun API Market.

数据来源：阿里云 API 市场「全国火车票查询（极速数据）」
- 接口地址：``http://jisutrainf.market.alicloudapi.com/train/station2s``
- 鉴权方式：请求头 ``Authorization: APPCODE <appcode>``
- 参数 ``start``/``end`` 为中文城市或车站名，``ishigh`` 控制是否仅高铁。

注意：该接口同样为付费接口，免费额度有限，默认开启 ``mock_mode`` 保护
额度。确认配额充足后，将 ``TRAIN_MOCK_MODE`` 设为 ``false`` 切换真实数据。
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from configs.settings import settings
from mcp_servers.base import BaseMCPServer

logger = logging.getLogger(__name__)

_HIGH_SPEED_TRAINS = ["G", "D", "C"]  # 高铁/动车/城际
_SEAT_TYPES = ["商务座", "一等座", "二等座", "无座"]


class TrainMCPServer(BaseMCPServer):
    """MCP server providing train ticket search via Aliyun API Market."""

    name = "Train Tools"
    description = "高铁/火车票查询工具集（阿里云 API 市场）"

    def __init__(self, mock_mode: Optional[bool] = None):
        """Initialize the train MCP server.

        Args:
            mock_mode: Override mock mode. Defaults to ``settings.train_mock_mode``.
        """
        super().__init__(
            mock_mode=settings.train_mock_mode if mock_mode is None else mock_mode
        )
        self.appcode = settings.aliyun_appcode
        self.base_url = settings.aliyun_train_url.rstrip("/")

    def _auth_headers(self) -> Dict[str, str]:
        """Build Authorization headers required by Aliyun API Market."""
        return {"Authorization": f"APPCODE {self.appcode}"}

    async def search_trains(
        self,
        start: str,
        end: str,
        date: str = "",
        is_high_speed: int = 0,
    ) -> Dict[str, Any]:
        """搜索指定出发/到达站点在指定日期的火车票。

        Args:
            start: 出发城市或车站（如 "杭州"）。
            end: 到达城市或车站（如 "北京"）。
            date: 出行日期（YYYY-MM-DD，可选）。
            is_high_speed: 是否仅查高铁（1 表示是，0 表示不限）。

        Returns:
            归一化后的火车票搜索结果。
        """
        if not start or not end:
            return self.error("出发站和到达站不能为空")

        if self.mock_mode:
            return _mock_search_trains(start, end, date, is_high_speed)

        params: Dict[str, Any] = {
            "start": start,
            "end": end,
            "ishigh": int(is_high_speed),
        }
        if date:
            params["date"] = date

        try:
            data = await self.get_json(
                self.base_url, params=params, headers=self._auth_headers()
            )
        except httpx.HTTPError as exc:
            logger.warning("火车票接口调用失败，降级为模拟数据: %s", exc)
            return _mock_search_trains(start, end, date, is_high_speed)

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

    def get_tools(self) -> list:
        """Get list of available tools (MCP schema)."""
        return [
            {
                "name": "search_trains",
                "description": "搜索高铁/火车票",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string", "description": "出发城市或车站"},
                        "end": {"type": "string", "description": "到达城市或车站"},
                        "date": {"type": "string", "description": "出行日期（YYYY-MM-DD）"},
                        "is_high_speed": {"type": "integer", "description": "是否仅高铁（1是0否）", "default": 0},
                    },
                    "required": ["start", "end"],
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
    """Normalize a single train item into the internal schema."""
    if not isinstance(item, dict):
        return item

    train_no = str(_pick(item, "trainNo", "train_no", "trainno", "checi", "trainCode") or "")
    seats = _extract_seats(item)
    return {
        "train_no": train_no,
        "train_type": _pick(item, "trainType", "train_type", "type") or _infer_type(train_no),
        "departure": start,
        "arrival": end,
        "departure_station": _pick(item, "startStation", "fromStation", "from", "start_station"),
        "arrival_station": _pick(item, "endStation", "toStation", "to", "end_station"),
        "departure_time": _pick(item, "startTime", "fromTime", "departureTime", "start_time"),
        "arrival_time": _pick(item, "endTime", "toTime", "arrivalTime", "end_time"),
        "duration": _pick(item, "runTime", "duration", "costTime", "travelTime"),
        "seats": seats,
        "price": _default_price(seats),
        "date": _pick(item, "date", "trainDate"),
    }


def _extract_seats(item: Dict[str, Any]) -> Dict[str, float]:
    """Extract seat price map from a train item (best-effort)."""
    seats: Dict[str, float] = {}
    # 常见席别字段名
    seat_fields = {
        "商务座": ("商务座", "businessSeat", "business"),
        "一等座": ("一等座", "firstSeat", "first"),
        "二等座": ("二等座", "secondSeat", "second"),
        "无座": ("无座", "noSeat", "noneSeat"),
        "硬座": ("硬座", "hardSeat"),
        "硬卧": ("硬卧", "hardSleep"),
        "软卧": ("软卧", "softSleep"),
    }
    for label, keys in seat_fields.items():
        value = _pick(item, *keys)
        if value is not None:
            try:
                seats[label] = float(value)
            except (TypeError, ValueError):
                pass
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


# ================================================================
# Mock data generators
# ================================================================

def _mock_search_trains(
    start: str, end: str, date: str, is_high_speed: int
) -> Dict[str, Any]:
    """Generate rich mock train search results."""
    prefixes = ["G", "D", "C"] if is_high_speed else ["G", "D", "C", "K", "T"]
    num_trains = random.randint(8, 12)
    trains = []
    for _ in range(num_trains):
        prefix = random.choice(prefixes)
        train_no = f"{prefix}{random.randint(100, 9999)}"
        dep_hour = random.randint(6, 21)
        dep_minute = random.choice([0, 10, 20, 30, 40, 50])
        duration_minutes = random.randint(90, 600)
        total_dep = dep_hour * 60 + dep_minute
        total_arr = total_dep + duration_minutes

        base_price = round(random.uniform(150, 900), 1)
        trains.append({
            "train_no": train_no,
            "train_type": _infer_type(train_no),
            "departure": start,
            "arrival": end,
            "departure_station": f"{start}东",
            "arrival_station": f"{end}南",
            "departure_time": f"{dep_hour:02d}:{dep_minute:02d}",
            "arrival_time": f"{total_arr // 60 % 24:02d}:{total_arr % 60:02d}",
            "duration": f"{duration_minutes // 60}小时{duration_minutes % 60}分",
            "seats": {
                "二等座": round(base_price, 1),
                "一等座": round(base_price * 1.6, 1),
                "商务座": round(base_price * 3.0, 1),
                "无座": round(base_price, 1),
            },
            "price": round(base_price, 1),
            "date": date or datetime.now().strftime("%Y-%m-%d"),
        })
    trains.sort(key=lambda x: x["departure_time"])
    return {
        "departure": start,
        "arrival": end,
        "date": date,
        "trains": trains,
        "total": len(trains),
        "source": "mock",
    }


# Global instance
train_mcp = TrainMCPServer()
