"""Itinerary Agent - handles itinerary planning and management."""

import logging
from typing import Any, Dict, List
from .base_agent import BaseAgent, AgentCard, Skill
from mcp_servers.db_mcp import db_mcp

logger = logging.getLogger(__name__)


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
