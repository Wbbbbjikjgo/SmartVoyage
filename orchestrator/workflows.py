"""Workflow definitions for multi-agent collaboration."""

import logging
from typing import Dict, Any, Optional
from datetime import date, timedelta
from orchestrator.agent_network import agent_network

logger = logging.getLogger(__name__)


class TravelPlanningWorkflow:
    """Workflow for planning a complete travel itinerary."""

    def __init__(self):
        """Initialize travel planning workflow."""
        self.network = agent_network

    async def execute(
        self,
        user_id: int,
        destination: str,
        start_date: str,
        duration: int,
        departure: str = None,
        budget: float = None,
        guests: int = 1,
    ) -> Dict[str, Any]:
        """
        Execute the travel planning workflow.

        Args:
            user_id: User ID
            destination: Destination city
            start_date: Start date (YYYY-MM-DD)
            duration: Duration in days
            departure: Departure city (optional)
            budget: Budget amount (optional)
            guests: Number of guests

        Returns:
            Complete itinerary with weather, flights, and hotels
        """
        result = {
            "destination": destination,
            "start_date": start_date,
            "duration": duration,
            "steps": [],
        }

        try:
            # Step 1: Get weather forecast
            logger.info(f"Step 1: Getting weather for {destination}")
            weather_result = await self.network.invoke_agent(
                "weather",
                "get_forecast",
                {"location": destination, "days": duration},
            )
            result["steps"].append({
                "step": "weather",
                "status": "success" if not weather_result.get("error") else "error",
                "data": weather_result,
            })
            result["weather"] = weather_result

            # Step 2: Search flights (if departure specified)
            if departure:
                logger.info(f"Step 2: Searching flights from {departure} to {destination}")
                flight_result = await self.network.invoke_agent(
                    "flight",
                    "search_flights",
                    {
                        "departure": departure,
                        "arrival": destination,
                        "date": start_date,
                        "passengers": guests,
                    },
                )
                result["steps"].append({
                    "step": "flights",
                    "status": "success" if not flight_result.get("error") else "error",
                    "data": flight_result,
                })
                result["flights"] = flight_result

            # Step 3: Search hotels
            # Calculate check-out date
            start = date.fromisoformat(start_date)
            check_out = start + timedelta(days=duration)
            check_out_str = check_out.isoformat()

            logger.info(f"Step 3: Searching hotels in {destination}")
            hotel_result = await self.network.invoke_agent(
                "hotel",
                "search_hotels",
                {
                    "location": destination,
                    "check_in": start_date,
                    "check_out": check_out_str,
                    "guests": guests,
                },
            )
            result["steps"].append({
                "step": "hotels",
                "status": "success" if not hotel_result.get("error") else "error",
                "data": hotel_result,
            })
            result["hotels"] = hotel_result

            # Step 4: Create itinerary
            logger.info(f"Step 4: Creating itinerary for user {user_id}")
            itinerary_result = await self.network.invoke_agent(
                "itinerary",
                "create_itinerary",
                {
                    "user_id": user_id,
                    "destination": destination,
                    "start_date": start_date,
                    "duration": duration,
                    "budget": budget,
                },
            )
            result["steps"].append({
                "step": "create_itinerary",
                "status": "success" if not itinerary_result.get("error") else "error",
                "data": itinerary_result,
            })

            if not itinerary_result.get("error"):
                itinerary_id = itinerary_result["itinerary_id"]

                # Step 5: Add flight booking (if available)
                if departure and result.get("flights") and not result["flights"].get("error"):
                    flights = result["flights"].get("flights", [])
                    if flights:
                        selected_flight = flights[0]
                        booking_result = await self.network.invoke_agent(
                            "itinerary",
                            "add_booking",
                            {
                                "itinerary_id": itinerary_id,
                                "booking_type": "flight",
                                "details": {
                                    "flight_no": selected_flight["flight_no"],
                                    "airline": selected_flight["airline"],
                                    "departure": selected_flight["departure"],
                                    "arrival": selected_flight["arrival"],
                                    "departure_time": selected_flight["departure_time"],
                                    "arrival_time": selected_flight["arrival_time"],
                                    "price": selected_flight["price"],
                                },
                            },
                        )
                        result["steps"].append({
                            "step": "book_flight",
                            "status": "success" if not booking_result.get("error") else "error",
                            "data": booking_result,
                        })

                # Step 6: Add hotel booking (if available)
                if result.get("hotels") and not result["hotels"].get("error"):
                    hotels = result["hotels"].get("hotels", [])
                    if hotels:
                        selected_hotel = hotels[0]
                        booking_result = await self.network.invoke_agent(
                            "itinerary",
                            "add_booking",
                            {
                                "itinerary_id": itinerary_id,
                                "booking_type": "hotel",
                                "details": {
                                    "hotel_name": selected_hotel["hotel_name"],
                                    "location": selected_hotel["location"],
                                    "price_per_night": selected_hotel["price_per_night"],
                                    "rating": selected_hotel["rating"],
                                },
                            },
                        )
                        result["steps"].append({
                            "step": "book_hotel",
                            "status": "success" if not booking_result.get("error") else "error",
                            "data": booking_result,
                        })

                result["itinerary_id"] = itinerary_id

            result["success"] = True

        except Exception as e:
            logger.exception(f"Error in travel planning workflow: {e}")
            result["success"] = False
            result["error"] = str(e)

        return result

    async def get_weather_only(self, location: str) -> Dict[str, Any]:
        """
        Get weather for a location (simplified workflow).

        Args:
            location: City name

        Returns:
            Weather data
        """
        return await self.network.invoke_agent(
            "weather",
            "get_current_weather",
            {"location": location},
        )

    async def search_flights_only(
        self,
        departure: str,
        arrival: str,
        date: str,
        passengers: int = 1,
    ) -> Dict[str, Any]:
        """
        Search flights only (simplified workflow).

        Args:
            departure: Departure city
            arrival: Arrival city
            date: Travel date
            passengers: Number of passengers

        Returns:
            Flight search results
        """
        return await self.network.invoke_agent(
            "flight",
            "search_flights",
            {
                "departure": departure,
                "arrival": arrival,
                "date": date,
                "passengers": passengers,
            },
        )

    async def search_hotels_only(
        self,
        location: str,
        check_in: str,
        check_out: str,
        guests: int = 2,
    ) -> Dict[str, Any]:
        """
        Search hotels only (simplified workflow).

        Args:
            location: City name
            check_in: Check-in date
            check_out: Check-out date
            guests: Number of guests

        Returns:
            Hotel search results
        """
        return await self.network.invoke_agent(
            "hotel",
            "search_hotels",
            {
                "location": location,
                "check_in": check_in,
                "check_out": check_out,
                "guests": guests,
            },
        )


# Global instance
travel_workflow = TravelPlanningWorkflow()
