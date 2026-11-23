"""Helpers for arranging provided real data into a day-by-day skeleton.

注意：真正的行程生成由 ``Itinerary Agent`` 的大模型完成（通过 A2A 调用）。
这里只保留一个纯函数工具，用于把「已经拿到的真实景点/天气数据」按天均分，
不生成、不编造任何外部数据。
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional


def format_day_weather(forecast: Optional[Dict[str, Any]]) -> str:
    """将单日预报数据格式化为可读字符串。"""
    if not forecast:
        return ""
    day = forecast.get("day_weather", "")
    day_temp = forecast.get("day_temp", "")
    night_temp = forecast.get("night_temp", "")
    if day_temp or night_temp:
        return f"{day} {night_temp}~{day_temp}°C".strip()
    return day


def build_day_plan(
    start_date: str,
    duration: int,
    weather: Optional[Dict[str, Any]],
    attractions: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """按天均分已提供的真实景点，并附上当天真实天气。

    Args:
        start_date: 开始日期（YYYY-MM-DD）。
        duration: 行程天数。
        weather: 天气预报结果（含 ``forecast`` 列表）。
        attractions: 景点列表（每项含 ``name``）。

    Returns:
        逐日安排列表（不含编造内容）。
    """
    try:
        start = date.fromisoformat(start_date)
    except (ValueError, TypeError):
        start = date.today()

    forecasts = (weather or {}).get("forecast", [])
    names = [
        item.get("name")
        for item in (attractions or [])
        if isinstance(item, dict) and item.get("name")
    ]

    days = []
    per_day = max(1, len(names) // max(duration, 1))
    idx = 0
    for day_index in range(duration):
        day_forecast = forecasts[day_index] if day_index < len(forecasts) else None
        day_attractions = names[idx: idx + per_day]
        idx += per_day
        days.append({
            "day": day_index + 1,
            "date": (start + timedelta(days=day_index)).isoformat(),
            "weather": format_day_weather(day_forecast),
            "attractions": day_attractions,
            "plan": "",
        })

    if idx < len(names) and days:
        days[-1]["attractions"].extend(names[idx:])

    return days
