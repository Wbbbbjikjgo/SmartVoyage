"""Pydantic schemas actually used by the runtime.

目前只有主 Agent 的意图识别会用到这里的结构：

- ``IntentType``：意图枚举；
- ``IntentResult``：意图 + 置信度 + 槽位。

外部数据（天气/航班/酒店/车次）由各 MCP Server 返回归一化后的 dict，
不再额外定义一套未使用的 Pydantic DTO。数据库实体见 ``models.database``。
"""

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """用户意图类型。"""

    WEATHER_QUERY = "weather_query"
    FLIGHT_BOOKING = "flight_booking"
    TRAIN_BOOKING = "train_booking"
    HOTEL_BOOKING = "hotel_booking"
    ITINERARY_PLANNING = "itinerary_planning"
    GENERAL_QA = "general_qa"


class IntentResult(BaseModel):
    """意图识别结果。"""

    intent: IntentType
    confidence: float = Field(..., ge=0, le=1)
    slots: Dict[str, Any] = Field(default_factory=dict)
