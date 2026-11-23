"""Data models used by SmartVoyage."""

from .database import (
    Base,
    Booking,
    Itinerary,
    User,
    close_db,
    get_engine,
    get_session_factory,
    init_db,
    seed_default_user,
)
from .schemas import IntentResult, IntentType

__all__ = [
    # Pydantic schemas
    "IntentType",
    "IntentResult",
    # SQLAlchemy models / helpers
    "Base",
    "User",
    "Itinerary",
    "Booking",
    "get_engine",
    "get_session_factory",
    "init_db",
    "seed_default_user",
    "close_db",
]
