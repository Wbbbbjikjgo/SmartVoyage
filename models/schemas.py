"""Pydantic schemas for data validation and serialization."""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from enum import Enum


# ============== Enums ==============

class IntentType(str, Enum):
    """User intent types."""
    WEATHER_QUERY = "weather_query"
    FLIGHT_BOOKING = "flight_booking"
    HOTEL_BOOKING = "hotel_booking"
    ITINERARY_PLANNING = "itinerary_planning"
    GENERAL_QA = "general_qa"


class ItineraryStatus(str, Enum):
    """Itinerary status."""
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class BookingType(str, Enum):
    """Booking type."""
    FLIGHT = "flight"
    HOTEL = "hotel"
    TICKET = "ticket"


class BookingStatus(str, Enum):
    """Booking status."""
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"


# ============== User Schemas ==============

class UserCreate(BaseModel):
    """Schema for creating a user."""
    name: str = Field(..., min_length=1, max_length=64)
    email: EmailStr
    preferences: Optional[Dict[str, Any]] = None


class UserResponse(BaseModel):
    """Schema for user response."""
    user_id: int
    name: str
    email: str
    preferences: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Itinerary Schemas ==============

class ItineraryCreate(BaseModel):
    """Schema for creating an itinerary."""
    user_id: int
    destination: str = Field(..., min_length=1, max_length=64)
    start_date: date
    duration: int = Field(..., gt=0)
    budget: Optional[Decimal] = Field(None, gt=0)


class ItineraryResponse(BaseModel):
    """Schema for itinerary response."""
    itinerary_id: int
    user_id: int
    destination: str
    start_date: date
    duration: int
    budget: Optional[Decimal] = None
    status: ItineraryStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============== Booking Schemas ==============

class BookingCreate(BaseModel):
    """Schema for creating a booking."""
    itinerary_id: int
    type: BookingType
    details: Dict[str, Any]
    status: BookingStatus = BookingStatus.PENDING


class BookingResponse(BaseModel):
    """Schema for booking response."""
    booking_id: int
    itinerary_id: int
    type: BookingType
    details: Dict[str, Any]
    status: BookingStatus
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Chat Schemas ==============

class ChatMessage(BaseModel):
    """Schema for chat message."""
    role: str = Field(..., description="Message role: user/assistant/system")
    content: str = Field(..., description="Message content")


class ChatResponse(BaseModel):
    """Schema for chat response."""
    message: str = Field(..., description="Assistant response message")
    intent: Optional[IntentType] = None
    data: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


# ============== Intent Recognition Schemas ==============

class IntentResult(BaseModel):
    """Schema for intent recognition result."""
    intent: IntentType
    confidence: float = Field(..., ge=0, le=1)
    slots: Dict[str, Any] = Field(default_factory=dict)


# ============== External Data Schemas ==============

class WeatherData(BaseModel):
    """Schema for weather data."""
    location: str
    temperature: float
    description: str
    humidity: int
    wind_speed: float
    icon: Optional[str] = None
    forecast: Optional[List[Dict[str, Any]]] = None


class FlightData(BaseModel):
    """Schema for flight data."""
    flight_no: str
    airline: str
    departure: str
    arrival: str
    departure_time: str
    arrival_time: str
    price: Decimal
    currency: str = "CNY"
    available_seats: int = 0


class HotelData(BaseModel):
    """Schema for hotel data."""
    hotel_name: str
    location: str
    price_per_night: Decimal
    currency: str = "CNY"
    rating: float = Field(..., ge=0, le=5)
    amenities: List[str] = Field(default_factory=list)
    image_url: Optional[str] = None
