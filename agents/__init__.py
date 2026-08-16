"""A2A Agent module for SmartVoyage."""

from .base_agent import BaseAgent, AgentCard, Skill
from .weather_agent import WeatherAgent
from .flight_agent import FlightAgent
from .hotel_agent import HotelAgent
from .train_agent import TrainAgent
from .itinerary_agent import ItineraryAgent

__all__ = [
    "BaseAgent",
    "AgentCard",
    "Skill",
    "WeatherAgent",
    "FlightAgent",
    "HotelAgent",
    "TrainAgent",
    "ItineraryAgent",
]
