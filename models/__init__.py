"""Data models module for SmartVoyage."""

from .schemas import (
    UserCreate,
    UserResponse,
    ItineraryCreate,
    ItineraryResponse,
    BookingCreate,
    BookingResponse,
    ChatMessage,
    ChatResponse,
    IntentResult,
    WeatherData,
    FlightData,
    TrainData,
    HotelData,
)
from .database import (
    Base,
    User,
    Itinerary,
    Booking,
    get_engine,
    get_session,
    init_db,
)

__all__ = [
    # Pydantic schemas
    "UserCreate",
    "UserResponse",
    "ItineraryCreate",
    "ItineraryResponse",
    "BookingCreate",
    "BookingResponse",
    "ChatMessage",
    "ChatResponse",
    "IntentResult",
    "WeatherData",
    "FlightData",
    "TrainData",
    "HotelData",
    # SQLAlchemy models
    "Base",
    "User",
    "Itinerary",
    "Booking",
    "get_engine",
    "get_session",
    "init_db",
]
