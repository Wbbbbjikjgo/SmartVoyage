"""Database MCP tool server for CRUD operations."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from sqlalchemy.orm import Session
from models.database import get_session_factory, User, Itinerary, Booking

logger = logging.getLogger(__name__)


class DatabaseMCPServer:
    """MCP server for database operations."""

    def __init__(self):
        """Initialize database MCP server."""
        self.name = "Database Tools"
        self.description = "数据库操作工具集"

    def _get_session(self) -> Session:
        """Get database session."""
        SessionFactory = get_session_factory()
        return SessionFactory()

    async def create_user(
        self,
        name: str,
        email: str,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new user.

        Args:
            name: User name
            email: User email
            preferences: User preferences (optional)

        Returns:
            Created user data
        """
        try:
            session = self._get_session()
            try:
                user = User(name=name, email=email, preferences=preferences)
                session.add(user)
                session.commit()
                session.refresh(user)

                return {
                    "user_id": user.user_id,
                    "name": user.name,
                    "email": user.email,
                    "preferences": user.preferences,
                    "created_at": user.created_at.isoformat(),
                }
            finally:
                session.close()

        except Exception as e:
            logger.exception(f"Error creating user: {e}")
            return {"error": True, "message": str(e)}

    async def get_user(self, user_id: int) -> Dict[str, Any]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User data
        """
        try:
            session = self._get_session()
            try:
                user = session.query(User).filter(User.user_id == user_id).first()
                if not user:
                    return {"error": True, "message": f"User not found: {user_id}"}

                return {
                    "user_id": user.user_id,
                    "name": user.name,
                    "email": user.email,
                    "preferences": user.preferences,
                    "created_at": user.created_at.isoformat(),
                }
            finally:
                session.close()

        except Exception as e:
            logger.exception(f"Error getting user: {e}")
            return {"error": True, "message": str(e)}

    async def create_itinerary(
        self,
        user_id: int,
        destination: str,
        start_date: str,
        duration: int,
        budget: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Create a new itinerary.

        Args:
            user_id: User ID
            destination: Destination city
            start_date: Start date (YYYY-MM-DD)
            duration: Duration in days
            budget: Budget amount (optional)

        Returns:
            Created itinerary data
        """
        try:
            session = self._get_session()
            try:
                itinerary = Itinerary(
                    user_id=user_id,
                    destination=destination,
                    start_date=date.fromisoformat(start_date),
                    duration=duration,
                    budget=budget,
                    status="draft",
                )
                session.add(itinerary)
                session.commit()
                session.refresh(itinerary)

                return {
                    "itinerary_id": itinerary.itinerary_id,
                    "user_id": itinerary.user_id,
                    "destination": itinerary.destination,
                    "start_date": itinerary.start_date.isoformat(),
                    "duration": itinerary.duration,
                    "budget": float(itinerary.budget) if itinerary.budget else None,
                    "status": itinerary.status,
                    "created_at": itinerary.created_at.isoformat(),
                }
            finally:
                session.close()

        except Exception as e:
            logger.exception(f"Error creating itinerary: {e}")
            return {"error": True, "message": str(e)}

    async def get_user_itineraries(self, user_id: int) -> Dict[str, Any]:
        """
        Get all itineraries for a user.

        Args:
            user_id: User ID

        Returns:
            List of itineraries
        """
        try:
            session = self._get_session()
            try:
                itineraries = (
                    session.query(Itinerary)
                    .filter(Itinerary.user_id == user_id)
                    .order_by(Itinerary.created_at.desc())
                    .all()
                )

                result = []
                for itin in itineraries:
                    result.append({
                        "itinerary_id": itin.itinerary_id,
                        "destination": itin.destination,
                        "start_date": itin.start_date.isoformat(),
                        "duration": itin.duration,
                        "budget": float(itin.budget) if itin.budget else None,
                        "status": itin.status,
                        "created_at": itin.created_at.isoformat(),
                    })

                return {"user_id": user_id, "itineraries": result, "total": len(result)}
            finally:
                session.close()

        except Exception as e:
            logger.exception(f"Error getting itineraries: {e}")
            return {"error": True, "message": str(e)}

    async def create_booking(
        self,
        itinerary_id: int,
        booking_type: str,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a new booking.

        Args:
            itinerary_id: Itinerary ID
            booking_type: Booking type (flight/hotel/ticket)
            details: Booking details

        Returns:
            Created booking data
        """
        try:
            session = self._get_session()
            try:
                booking = Booking(
                    itinerary_id=itinerary_id,
                    type=booking_type,
                    details=details,
                    status="pending",
                )
                session.add(booking)
                session.commit()
                session.refresh(booking)

                return {
                    "booking_id": booking.booking_id,
                    "itinerary_id": booking.itinerary_id,
                    "type": booking.type,
                    "details": booking.details,
                    "status": booking.status,
                    "created_at": booking.created_at.isoformat(),
                }
            finally:
                session.close()

        except Exception as e:
            logger.exception(f"Error creating booking: {e}")
            return {"error": True, "message": str(e)}

    async def get_itinerary_bookings(self, itinerary_id: int) -> Dict[str, Any]:
        """
        Get all bookings for an itinerary.

        Args:
            itinerary_id: Itinerary ID

        Returns:
            List of bookings
        """
        try:
            session = self._get_session()
            try:
                bookings = (
                    session.query(Booking)
                    .filter(Booking.itinerary_id == itinerary_id)
                    .order_by(Booking.created_at.desc())
                    .all()
                )

                result = []
                for booking in bookings:
                    result.append({
                        "booking_id": booking.booking_id,
                        "type": booking.type,
                        "details": booking.details,
                        "status": booking.status,
                        "created_at": booking.created_at.isoformat(),
                    })

                return {
                    "itinerary_id": itinerary_id,
                    "bookings": result,
                    "total": len(result),
                }
            finally:
                session.close()

        except Exception as e:
            logger.exception(f"Error getting bookings: {e}")
            return {"error": True, "message": str(e)}

    def get_tools(self) -> list:
        """Get list of available tools."""
        return [
            {
                "name": "create_user",
                "description": "创建新用户",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "用户姓名"},
                        "email": {"type": "string", "description": "用户邮箱"},
                        "preferences": {
                            "type": "object",
                            "description": "用户偏好",
                        },
                    },
                    "required": ["name", "email"],
                },
            },
            {
                "name": "get_user",
                "description": "获取用户信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "用户ID"},
                    },
                    "required": ["user_id"],
                },
            },
            {
                "name": "create_itinerary",
                "description": "创建新行程",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "用户ID"},
                        "destination": {"type": "string", "description": "目的地"},
                        "start_date": {
                            "type": "string",
                            "description": "开始日期（YYYY-MM-DD）",
                        },
                        "duration": {"type": "integer", "description": "行程天数"},
                        "budget": {"type": "number", "description": "预算"},
                    },
                    "required": ["user_id", "destination", "start_date", "duration"],
                },
            },
            {
                "name": "get_user_itineraries",
                "description": "获取用户的所有行程",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "用户ID"},
                    },
                    "required": ["user_id"],
                },
            },
            {
                "name": "create_booking",
                "description": "创建新预订",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "itinerary_id": {
                            "type": "integer",
                            "description": "行程ID",
                        },
                        "booking_type": {
                            "type": "string",
                            "description": "预订类型（flight/hotel/ticket）",
                        },
                        "details": {
                            "type": "object",
                            "description": "预订详情",
                        },
                    },
                    "required": ["itinerary_id", "booking_type", "details"],
                },
            },
            {
                "name": "get_itinerary_bookings",
                "description": "获取行程的所有预订",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "itinerary_id": {
                            "type": "integer",
                            "description": "行程ID",
                        },
                    },
                    "required": ["itinerary_id"],
                },
            },
        ]


# Global instance
db_mcp = DatabaseMCPServer()
