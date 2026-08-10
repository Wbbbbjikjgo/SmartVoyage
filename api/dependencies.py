"""API dependencies."""

from typing import Optional
from fastapi import Header, HTTPException
from core.context_manager import context_manager


def get_current_session(session_id: Optional[str] = Header(None)) -> str:
    """
    Get or create session from header.

    Args:
        session_id: Session ID from header

    Returns:
        Session ID
    """
    if not session_id:
        # Create new session
        session_id = context_manager.create_session()
    else:
        # Verify session exists
        session = context_manager.get_session(session_id)
        if not session:
            # Create session with given ID
            context_manager.sessions[session_id] = {
                "session_id": session_id,
                "created_at": None,
                "messages": [],
                "user_id": None,
                "current_intent": None,
                "slots": {},
                "history": [],
            }

    return session_id
