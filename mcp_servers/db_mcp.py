"""Database MCP Server (stdio) for real CRUD operations.

启动方式::

    python -m mcp_servers.db_mcp

所有操作都直接读写本地 MySQL，不包含任何模拟数据。
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session

from mcp_servers.base import configure_stdio_logging, dump
from models.database import Booking, Itinerary, User, get_session_factory

logger = logging.getLogger(__name__)

mcp = FastMCP("smartvoyage_db", log_level="ERROR")


class DatabaseMCPServer:
    """MCP server for database operations."""

    name = "Database Tools"
    description = "数据库操作工具集（MySQL 真实数据）"

    def _get_session(self) -> Session:
        """Get a database session."""
        SessionFactory = get_session_factory()
        return SessionFactory()

    async def create_user(
        self,
        name: str,
        email: str,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new user."""
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
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as JSON
            logger.exception("Error creating user")
            return {"error": True, "message": str(exc)}

    async def get_user(self, user_id: int) -> Dict[str, Any]:
        """Get user by ID."""
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
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error getting user")
            return {"error": True, "message": str(exc)}

    async def create_itinerary(
        self,
        user_id: int,
        destination: str,
        start_date: str,
        duration: int,
        budget: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Create a new itinerary."""
        try:
            from datetime import date

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
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error creating itinerary")
            return {"error": True, "message": str(exc)}

    async def get_user_itineraries(self, user_id: int) -> Dict[str, Any]:
        """Get all itineraries for a user."""
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
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error getting itineraries")
            return {"error": True, "message": str(exc)}

    async def create_booking(
        self,
        itinerary_id: int,
        booking_type: str,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a new booking."""
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
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error creating booking")
            return {"error": True, "message": str(exc)}

    async def get_itinerary_bookings(self, itinerary_id: int) -> Dict[str, Any]:
        """Get all bookings for an itinerary."""
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
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error getting bookings")
            return {"error": True, "message": str(exc)}

    async def update_itinerary_status(
        self, itinerary_id: int, status: str
    ) -> Dict[str, Any]:
        """Update the status of an itinerary."""
        valid_status = {"draft", "confirmed", "cancelled"}
        if status not in valid_status:
            return {"error": True, "message": f"非法状态: {status}"}

        try:
            session = self._get_session()
            try:
                itinerary = (
                    session.query(Itinerary)
                    .filter(Itinerary.itinerary_id == itinerary_id)
                    .first()
                )
                if not itinerary:
                    return {"error": True, "message": f"Itinerary not found: {itinerary_id}"}
                itinerary.status = status
                session.commit()
                return {
                    "itinerary_id": itinerary.itinerary_id,
                    "status": itinerary.status,
                    "updated_at": itinerary.updated_at.isoformat(),
                }
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error updating itinerary status")
            return {"error": True, "message": str(exc)}

    async def cancel_booking(self, booking_id: int) -> Dict[str, Any]:
        """Cancel a booking."""
        try:
            session = self._get_session()
            try:
                booking = (
                    session.query(Booking)
                    .filter(Booking.booking_id == booking_id)
                    .first()
                )
                if not booking:
                    return {"error": True, "message": f"Booking not found: {booking_id}"}
                booking.status = "cancelled"
                session.commit()
                return {"booking_id": booking.booking_id, "status": booking.status}
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error cancelling booking")
            return {"error": True, "message": str(exc)}


db_server = DatabaseMCPServer()


# ================================================================
# MCP Tools
# ================================================================

@mcp.tool()
async def create_user(
    name: str, email: str, preferences: Optional[Dict[str, Any]] = None
) -> str:
    """创建新用户。"""
    return dump(await db_server.create_user(name, email, preferences))


@mcp.tool()
async def get_user(user_id: int) -> str:
    """获取用户信息。"""
    return dump(await db_server.get_user(user_id))


@mcp.tool()
async def create_itinerary(
    user_id: int,
    destination: str,
    start_date: str,
    duration: int,
    budget: Optional[float] = None,
) -> str:
    """创建新行程。

    Args:
        user_id: 用户 ID。
        destination: 目的地城市。
        start_date: 开始日期（YYYY-MM-DD）。
        duration: 行程天数。
        budget: 预算（可选）。
    """
    return dump(
        await db_server.create_itinerary(
            user_id, destination, start_date, duration, budget
        )
    )


@mcp.tool()
async def get_user_itineraries(user_id: int) -> str:
    """获取用户的所有行程。"""
    return dump(await db_server.get_user_itineraries(user_id))


@mcp.tool()
async def get_itinerary_bookings(itinerary_id: int) -> str:
    """获取行程的所有预订。"""
    return dump(await db_server.get_itinerary_bookings(itinerary_id))


@mcp.tool()
async def create_booking(
    itinerary_id: int, booking_type: str, details: Dict[str, Any]
) -> str:
    """创建新预订。

    Args:
        itinerary_id: 行程 ID。
        booking_type: 预订类型（flight/hotel/ticket）。
        details: 预订详情。
    """
    return dump(
        await db_server.create_booking(itinerary_id, booking_type, details)
    )


@mcp.tool()
async def update_itinerary_status(itinerary_id: int, status: str) -> str:
    """更新行程状态（draft/confirmed/cancelled）。"""
    return dump(await db_server.update_itinerary_status(itinerary_id, status))


@mcp.tool()
async def cancel_booking(booking_id: int) -> str:
    """取消预订。"""
    return dump(await db_server.cancel_booking(booking_id))


if __name__ == "__main__":
    configure_stdio_logging()
    mcp.run(transport="stdio")
