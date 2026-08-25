"""In-memory session manager with random IDs and expiration."""

from __future__ import annotations

import asyncio
import secrets
import string
import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import WebSocket

from app.config import settings


def _generate_id(length: int = 6) -> str:
    """Generate a random alphanumeric session ID (uppercase)."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _generate_token() -> str:
    """Generate a secure random token."""
    return secrets.token_hex(16)


@dataclass
class Session:
    """A single interview session."""

    session_id: str
    host_token: str
    viewer_token: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    is_active: bool = True

    # Connected WebSocket clients
    host_ws: Optional[WebSocket] = field(default=None, repr=False)
    viewer_ws_list: list[WebSocket] = field(default_factory=list, repr=False)

    # Pipeline state
    current_transcript: str = ""
    last_question: str = ""
    last_answer: str = ""

    def __post_init__(self) -> None:
        if self.expires_at == 0.0:
            self.expires_at = self.created_at + (settings.session_expiry_minutes * 60)

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    async def broadcast_to_viewers(self, message: dict) -> None:
        """Send a JSON message to all connected viewers."""
        import json

        data = json.dumps(message)
        dead: list[WebSocket] = []
        for ws in self.viewer_ws_list:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.viewer_ws_list.remove(ws)


class SessionManager:
    """Manages all active sessions in memory."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    def create_session(self) -> Session:
        """Create a new session with random ID and tokens."""
        # Ensure unique ID
        session_id = _generate_id(settings.session_id_length)
        while session_id in self._sessions:
            session_id = _generate_id(settings.session_id_length)

        session = Session(
            session_id=session_id,
            host_token=_generate_token(),
            viewer_token=_generate_token(),
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID, returns None if expired or not found."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.is_expired:
            self._sessions.pop(session_id, None)
            return None
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        return self._sessions.pop(session_id, None) is not None

    def start_cleanup_loop(self) -> None:
        """Start a background task to clean up expired sessions."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    def stop_cleanup_loop(self) -> None:
        """Stop the cleanup background task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            self._cleanup_task = None

    async def _cleanup_loop(self) -> None:
        """Periodically remove expired sessions."""
        while True:
            await asyncio.sleep(60)
            now = time.time()
            expired = [
                sid
                for sid, s in self._sessions.items()
                if now > s.expires_at
            ]
            for sid in expired:
                self._sessions.pop(sid, None)


# Singleton instance
session_manager = SessionManager()
