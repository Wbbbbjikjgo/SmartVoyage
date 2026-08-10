"""Context manager for maintaining conversation state."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages conversation context and state."""

    def __init__(self):
        """Initialize context manager."""
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self) -> str:
        """
        Create a new session.

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "session_id": session_id,
            "created_at": datetime.utcnow().isoformat(),
            "messages": [],
            "user_id": None,
            "current_intent": None,
            "slots": {},
            "history": [],
        }
        logger.info(f"Created session: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session data or None
        """
        return self.sessions.get(session_id)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """
        Add a message to session history.

        Args:
            session_id: Session ID
            role: Message role (user/assistant/system)
            content: Message content
            metadata: Additional metadata

        Returns:
            True if successful
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        session["messages"].append(message)
        return True

    def update_intent(self, session_id: str, intent: str) -> bool:
        """
        Update current intent for session.

        Args:
            session_id: Session ID
            intent: New intent

        Returns:
            True if successful
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        # Save previous intent to history
        if session["current_intent"]:
            session["history"].append({
                "intent": session["current_intent"],
                "slots": session["slots"].copy(),
                "timestamp": datetime.utcnow().isoformat(),
            })

        session["current_intent"] = intent
        session["slots"] = {}  # Reset slots for new intent
        return True

    def update_slots(self, session_id: str, slots: Dict[str, Any]) -> bool:
        """
        Update slots for current intent.

        Args:
            session_id: Session ID
            slots: Slots to update

        Returns:
            True if successful
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        session["slots"].update(slots)
        return True

    def set_user_id(self, session_id: str, user_id: int) -> bool:
        """
        Set user ID for session.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            True if successful
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        session["user_id"] = user_id
        return True

    def get_messages(
        self,
        session_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get recent messages from session.

        Args:
            session_id: Session ID
            limit: Maximum number of messages

        Returns:
            List of messages
        """
        session = self.sessions.get(session_id)
        if not session:
            return []

        return session["messages"][-limit:]

    def get_context_for_llm(self, session_id: str) -> List[Dict[str, str]]:
        """
        Get conversation context formatted for LLM.

        Args:
            session_id: Session ID

        Returns:
            List of message dicts for LLM
        """
        session = self.sessions.get(session_id)
        if not session:
            return []

        messages = []
        for msg in session["messages"][-10:]:  # Last 10 messages
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        return messages

    def clear_session(self, session_id: str) -> bool:
        """
        Clear session data.

        Args:
            session_id: Session ID

        Returns:
            True if successful
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Cleared session: {session_id}")
            return True
        return False

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get session summary.

        Args:
            session_id: Session ID

        Returns:
            Session summary
        """
        session = self.sessions.get(session_id)
        if not session:
            return {}

        return {
            "session_id": session_id,
            "created_at": session["created_at"],
            "user_id": session["user_id"],
            "current_intent": session["current_intent"],
            "slots": session["slots"],
            "message_count": len(session["messages"]),
            "history_count": len(session["history"]),
        }


# Global instance
context_manager = ContextManager()
