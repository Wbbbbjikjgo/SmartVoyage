"""Itinerary Agent - handles itinerary planning and management."""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from .base_agent import BaseAgent, AgentCard, Skill
from mcp_servers.db_mcp import db_mcp
from mcp_servers.weather_mcp import weather_mcp
from mcp_servers.hotel_mcp import hotel_mcp

logger = logging.getLogger(__name__)


def _format_day_weather(forecast: Optional[Dict[str, Any]]) -> str:
    """将单日预报数据格式化为可读字符串。"""
    if not forecast:
        return ""
    day = forecast.get("day_weather", "")
    day_temp = forecast.get("day_temp", "")
    night_temp = forecast.get("night_temp", "")
    if day_temp or night_temp:
        return f"{day} {night_temp}~{day_temp}°C".strip()
    return day


class ItineraryAgent(BaseAgent):
    """Agent for itinerary planning and lifecycle management."""

    def __init__(self):
        """Initialize itinerary agent."""
        super().__init__(
            name="Itinerary Agent",
            description="提供行程创建、查询、更新、取消等全生命周期管理服务",
            version="2.0.0",
        )

        self.register_skill(
            Skill(name="create_itinerary", description="创建新行程", tags=["itinerary", "planning"])
        )
        self.register_skill(
            Skill(name="plan_trip", description="规划完整行程（天气+景点+酒店+逐日安排）", tags=["itinerary", "planning"])
        )
        self.register_skill(
            Skill(name="get_user_itineraries", description="获取用户的所有行程", tags=["itinerary", "list"])
        )
        self.register_skill(
            Skill(name="get_itinerary_detail", description="获取行程详情及预订", tags=["itinerary", "detail"])
        )
        self.register_skill(
            Skill(name="add_booking", description="为行程添加预订", tags=["itinerary", "booking"])
        )
        self.register_skill(
            Skill(name="update_itinerary_status", description="更新行程状态", tags=["itinerary", "status"])
        )
        self.register_skill(
            Skill(name="cancel_booking", description="取消预订", tags=["itinerary", "booking"])
        )

    def get_agent_card(self, base_url: str) -> AgentCard:
        """Get agent card for A2A protocol."""
        return AgentCard(
            name=self.name,
            description=self.description,
            version=self.version,
            url=base_url,
            skills=self.skills,
            capabilities={
                "streaming": False,
                "pushNotifications": False,
            },
        )

    async def handle_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming task request."""
        skill_name = task.get("skill")
        parameters = task.get("parameters", {})

        if not skill_name:
            return {"error": True, "message": "No skill specified"}

        return await self.execute_skill(skill_name, parameters)

    async def skill_create_itinerary(
        self,
        user_id: int,
        destination: str,
        start_date: str,
        duration: int,
        budget: float = None,
    ) -> Dict[str, Any]:
        """创建新行程。"""
        return await db_mcp.create_itinerary(
            user_id=user_id,
            destination=destination,
            start_date=start_date,
            duration=duration,
            budget=budget,
        )

    async def skill_plan_trip(
        self,
        user_id: int,
        destination: str,
        start_date: str,
        duration: int,
        budget: float = None,
        guests: int = 1,
    ) -> Dict[str, Any]:
        """规划完整行程：天气 + 景点 + 酒店 + 逐日安排，并持久化到数据库。

        Args:
            user_id: 用户 ID。
            destination: 目的地城市。
            start_date: 出发日期（YYYY-MM-DD）。
            duration: 行程天数。
            budget: 预算（可选）。
            guests: 人数。

        Returns:
            包含逐日安排、天气、景点、酒店的详细行程。
        """
        # 1. 天气预报（高德，最多 4 天）
        weather = await weather_mcp.get_forecast(destination, min(duration, 4))

        # 2. 景点（高德 POI，按天数放大数量）
        attractions = await hotel_mcp.search_attractions(
            destination, limit=max(duration * 3, 6)
        )

        # 3. 酒店
        try:
            check_out = (date.fromisoformat(start_date) + timedelta(days=duration)).isoformat()
        except ValueError:
            check_out = ""
        hotels = await hotel_mcp.search_hotels(
            destination, start_date, check_out, guests
        )

        # 4. 创建行程记录（持久化）
        itinerary = await db_mcp.create_itinerary(
            user_id=user_id,
            destination=destination,
            start_date=start_date,
            duration=duration,
            budget=budget,
        )

        # 5. 生成逐日安排
        days = self._build_day_plan(start_date, duration, weather, attractions)

        return {
            "itinerary_id": itinerary.get("itinerary_id"),
            "destination": destination,
            "start_date": start_date,
            "duration": duration,
            "budget": budget,
            "weather": weather if not weather.get("error") else None,
            "attractions": attractions.get("attractions", [])
            if not attractions.get("error")
            else [],
            "hotels": hotels.get("hotels", []) if not hotels.get("error") else [],
            "days": days,
        }

    def _build_day_plan(
        self,
        start_date: str,
        duration: int,
        weather: Dict[str, Any],
        attractions: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """根据天气和景点，把行程拆成逐日安排（按天均分景点）。"""
        try:
            start = date.fromisoformat(start_date)
        except ValueError:
            start = date.today()

        forecasts = (weather or {}).get("forecast", [])
        names = [
            a.get("name")
            for a in attractions.get("attractions", [])
            if isinstance(a, dict) and a.get("name")
        ]

        days = []
        per_day = max(1, len(names) // max(duration, 1))
        idx = 0
        for d in range(duration):
            day_forecast = forecasts[d] if d < len(forecasts) else None
            day_attractions = names[idx : idx + per_day]
            idx += per_day
            days.append({
                "day": d + 1,
                "date": (start + timedelta(days=d)).isoformat(),
                "weather": _format_day_weather(day_forecast),
                "attractions": day_attractions,
            })

        # 剩余未分配的景点并入最后一天
        if idx < len(names) and days:
            days[-1]["attractions"].extend(names[idx:])

        return days

    async def skill_get_user_itineraries(self, user_id: int) -> Dict[str, Any]:
        """获取用户的所有行程。"""
        return await db_mcp.get_user_itineraries(user_id)

    async def skill_get_itinerary_detail(self, itinerary_id: int) -> Dict[str, Any]:
        """获取行程详情（含所有预订）。"""
        bookings_result = await db_mcp.get_itinerary_bookings(itinerary_id)
        if bookings_result.get("error"):
            return bookings_result

        return {
            "itinerary_id": itinerary_id,
            "bookings": bookings_result.get("bookings", []),
            "total_bookings": bookings_result.get("total", 0),
        }

    async def skill_add_booking(
        self,
        itinerary_id: int,
        booking_type: str,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """为行程添加预订。"""
        return await db_mcp.create_booking(itinerary_id, booking_type, details)

    async def skill_update_itinerary_status(
        self, itinerary_id: int, status: str
    ) -> Dict[str, Any]:
        """更新行程状态（draft/confirmed/cancelled）。"""
        return await db_mcp.update_itinerary_status(itinerary_id, status)

    async def skill_cancel_booking(self, booking_id: int) -> Dict[str, Any]:
        """取消预订。"""
        return await db_mcp.cancel_booking(booking_id)

    async def plan_itinerary(
        self,
        user_id: int,
        destination: str,
        start_date: str,
        duration: int,
        weather_data: Dict[str, Any] = None,
        flight_data: Dict[str, Any] = None,
        hotel_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Plan a complete itinerary with weather, flights, and hotels.

        Args:
            user_id: User ID
            destination: Destination city
            start_date: Start date
            duration: Duration in days
            weather_data: Weather forecast data
            flight_data: Flight search results
            hotel_data: Hotel search results

        Returns:
            Planned itinerary detail
        """
        itinerary_result = await self.skill_create_itinerary(
            user_id=user_id,
            destination=destination,
            start_date=start_date,
            duration=duration,
        )

        if itinerary_result.get("error"):
            return itinerary_result

        itinerary_id = itinerary_result["itinerary_id"]

        if flight_data and not flight_data.get("error"):
            flights = flight_data.get("flights", [])
            if flights:
                selected_flight = flights[0]
                await self.skill_add_booking(
                    itinerary_id=itinerary_id,
                    booking_type="flight",
                    details={
                        "flight_no": selected_flight.get("flight_no"),
                        "airline": selected_flight.get("airline"),
                        "departure": selected_flight.get("departure"),
                        "arrival": selected_flight.get("arrival"),
                        "departure_time": selected_flight.get("departure_time"),
                        "arrival_time": selected_flight.get("arrival_time"),
                        "price": selected_flight.get("price"),
                    },
                )

        if hotel_data and not hotel_data.get("error"):
            hotels = hotel_data.get("hotels", [])
            if hotels:
                selected_hotel = hotels[0]
                await self.skill_add_booking(
                    itinerary_id=itinerary_id,
                    booking_type="hotel",
                    details={
                        "hotel_name": selected_hotel.get("hotel_name"),
                        "location": selected_hotel.get("district") or selected_hotel.get("city"),
                        "price_per_night": selected_hotel.get("price_per_night"),
                        "rating": selected_hotel.get("rating"),
                    },
                )

        return await self.skill_get_itinerary_detail(itinerary_id)


# Global instance
itinerary_agent = ItineraryAgent()
