"""Slot filling for extracting structured information from user input."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, date, timedelta
import re

logger = logging.getLogger(__name__)


class SlotFiller:
    """Fills slots (extracts structured info) from user input."""

    def __init__(self):
        """Initialize slot filler."""
        pass

    def fill_slots(self, user_input: str, initial_slots: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Fill slots from user input.

        Args:
            user_input: User's natural language input
            initial_slots: Initial slots from intent recognition

        Returns:
            Filled slots dictionary
        """
        slots = initial_slots.copy() if initial_slots else {}

        # Normalize relative dates the LLM may have kept as text
        for key in ("date", "check_in", "check_out", "start_date"):
            if key in slots and isinstance(slots[key], str):
                normalized = self._normalize_date_text(slots[key])
                if normalized:
                    slots[key] = normalized

        # Extract departure city first (needed to exclude from destination)
        if "departure" not in slots:
            departure = self._extract_departure(user_input)
            if departure:
                slots["departure"] = departure

        # Extract destination city (excluding departure city)
        if "destination" not in slots:
            destination = self._extract_city(user_input, exclude=slots.get("departure"))
            if destination:
                slots["destination"] = destination

        # Extract dates
        if "date" not in slots:
            date_str = self._extract_date(user_input)
            if date_str:
                slots["date"] = date_str

        # Extract duration
        if "duration" not in slots:
            duration = self._extract_duration(user_input)
            if duration:
                slots["duration"] = duration

        # Extract budget
        if "budget" not in slots:
            budget = self._extract_budget(user_input)
            if budget:
                slots["budget"] = budget

        # Extract number of guests
        if "guests" not in slots:
            guests = self._extract_guests(user_input)
            if guests:
                slots["guests"] = guests

        return slots

    def _normalize_date_text(self, text: str) -> Optional[str]:
        """Normalize relative date text (e.g. '明天') to ISO date."""
        today = date.today()
        text = text.strip()
        if text == "今天":
            return today.isoformat()
        if text == "明天":
            return (today + timedelta(days=1)).isoformat()
        if text == "后天":
            return (today + timedelta(days=2)).isoformat()
        # Already an ISO date
        if re.match(r"\d{4}-\d{2}-\d{2}", text):
            return text
        # Chinese date formats: "8月15日" / "8月15号" / "2026年8月15日"
        match = re.search(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})[日号]", text)
        if match:
            year = int(match.group(1)) if match.group(1) else today.year
            month, day = int(match.group(2)), int(match.group(3))
            try:
                target = date(year, month, day)
                # If date already passed this year and no year specified, use next year
                if not match.group(1) and target < today:
                    target = date(year + 1, month, day)
                return target.isoformat()
            except ValueError:
                return None
        return None

    def _extract_city(self, text: str, exclude: Optional[str] = None) -> Optional[str]:
        """Extract city name from text, optionally excluding a city."""
        # Common Chinese cities
        cities = [
            "北京", "上海", "广州", "深圳", "成都", "杭州", "西安", "重庆",
            "武汉", "南京", "天津", "长沙", "青岛", "大连", "厦门", "昆明",
            "三亚", "海口", "苏州", "无锡", "郑州", "合肥", "福州", "哈尔滨",
            "沈阳", "济南", "石家庄", "太原", "兰州", "银川", "西宁", "乌鲁木齐",
            "拉萨", "贵阳", "南宁", "呼和浩特",
        ]

        # Prefer destination pattern "到X" (e.g. "从上海到北京" -> 北京)
        to_match = re.search(r"到(.{2,4}?)(?:的|市|$|[\s，。])", text)
        if to_match and to_match.group(1) in cities and to_match.group(1) != exclude:
            return to_match.group(1)

        # Otherwise return the first city in text order (by position, not list order)
        candidates = [(text.find(c), c) for c in cities if c in text and c != exclude]
        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[-1][1] if len(candidates) > 1 and exclude else candidates[0][1]

        return None

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from text."""
        # Try to find explicit date patterns (YYYY-MM-DD, YYYY/MM/DD)
        date_pattern = r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})"
        match = re.search(date_pattern, text)
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"

        # Try relative dates
        today = date.today()

        # "今天"
        if "今天" in text:
            return today.isoformat()

        # "明天"
        if "明天" in text:
            return (today + timedelta(days=1)).isoformat()

        # "后天"
        if "后天" in text:
            return (today + timedelta(days=2)).isoformat()

        # Chinese date formats via normalizer
        normalized = self._normalize_date_text(text)
        if normalized:
            return normalized

        # "下周X"
        weekday_map = {
            "一": 0, "二": 1, "三": 2, "四": 3,
            "五": 4, "六": 5, "日": 6, "天": 6,
        }
        for day_name, day_num in weekday_map.items():
            if f"下周{day_name}" in text:
                days_ahead = day_num - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                days_ahead += 7  # Next week
                return (today + timedelta(days=days_ahead)).isoformat()

        # "X天后"
        days_pattern = r"(\d+)\s*天后"
        match = re.search(days_pattern, text)
        if match:
            days = int(match.group(1))
            return (today + timedelta(days=days)).isoformat()

        return None

    def _extract_duration(self, text: str) -> Optional[int]:
        """Extract duration (number of days) from text."""
        # "X天"
        duration_pattern = r"(\d+)\s*[天日]"
        match = re.search(duration_pattern, text)
        if match:
            return int(match.group(1))

        # "一周" / "一个星期"
        if "一周" in text or "一个星期" in text:
            return 7

        # "半个月"
        if "半个月" in text:
            return 15

        return None

    def _extract_budget(self, text: str) -> Optional[float]:
        """Extract budget from text."""
        # "X元" / "X块"
        budget_pattern = r"(\d+)\s*[元块]"
        match = re.search(budget_pattern, text)
        if match:
            return float(match.group(1))

        # "预算X"
        budget_pattern2 = r"预算\s*(\d+)"
        match = re.search(budget_pattern2, text)
        if match:
            return float(match.group(1))

        # "X千"
        thousand_pattern = r"(\d+)\s*千"
        match = re.search(thousand_pattern, text)
        if match:
            return float(match.group(1)) * 1000

        # "X万"
        ten_thousand_pattern = r"(\d+)\s*万"
        match = re.search(ten_thousand_pattern, text)
        if match:
            return float(match.group(1)) * 10000

        return None

    def _extract_guests(self, text: str) -> Optional[int]:
        """Extract number of guests from text."""
        # "X人"
        guests_pattern = r"(\d+)\s*人"
        match = re.search(guests_pattern, text)
        if match:
            return int(match.group(1))

        # "两个人" / "两人"
        if "两个人" in text or "两人" in text:
            return 2

        # "三个人" / "三人"
        if "三个人" in text or "三人" in text:
            return 3

        return None

    def _extract_departure(self, text: str) -> Optional[str]:
        """Extract departure city from text."""
        # Look for "从X出发" / "从X到"
        departure_patterns = [
            r"从(.+?)出发",
            r"从(.+?)到",
        ]

        for pattern in departure_patterns:
            match = re.search(pattern, text)
            if match:
                city = match.group(1)
                # Validate it's a city
                if len(city) <= 4:  # City names are usually short
                    return city

        return None


# Global instance
slot_filler = SlotFiller()
