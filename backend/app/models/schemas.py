"""Pydantic models for all WebSocket message types."""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class SessionCreate(BaseModel):
    """Response when creating a new session."""
    session_id: str
    host_token: str
    viewer_token: str


class SessionInfo(BaseModel):
    """Public session info."""
    session_id: str
    created_at: float
    expires_at: float
    is_active: bool


# ---------------------------------------------------------------------------
# WebSocket message types
# ---------------------------------------------------------------------------

class WSMessageType(str, Enum):
    TRANSCRIPT = "transcript"
    QUESTION = "question"
    ANSWER_START = "answer_start"
    ANSWER_DELTA = "answer_delta"
    ANSWER_COMPLETE = "answer_complete"
    STATUS = "status"
    ERROR = "error"


class TranscriptStatus(str, Enum):
    PARTIAL = "partial"
    FINAL = "final"


class TranscriptMessage(BaseModel):
    type: str = WSMessageType.TRANSCRIPT
    status: TranscriptStatus
    text: str
    timestamp: Optional[float] = None


class QuestionMessage(BaseModel):
    type: str = WSMessageType.QUESTION
    text: str
    category: Optional[str] = None
    timestamp: Optional[float] = None


class AnswerStartMessage(BaseModel):
    type: str = WSMessageType.ANSWER_START
    question: str


class AnswerDeltaMessage(BaseModel):
    type: str = WSMessageType.ANSWER_DELTA
    text: str


class AnswerCompleteMessage(BaseModel):
    type: str = WSMessageType.ANSWER_COMPLETE
    question: str
    full_text: str


class StatusState(str, Enum):
    CONNECTING = "connecting"
    LISTENING = "listening"
    PROCESSING = "processing"
    GENERATING = "generating"
    ERROR = "error"
    IDLE = "idle"


class StatusMessage(BaseModel):
    type: str = WSMessageType.STATUS
    state: StatusState
    detail: str = ""


class ErrorMessage(BaseModel):
    type: str = WSMessageType.ERROR
    detail: str
