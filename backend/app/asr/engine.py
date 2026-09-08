"""Abstract ASR engine interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, AsyncIterator

import numpy as np


@dataclass
class TranscriptResult:
    """A single transcription result."""

    text: str
    is_final: bool
    confidence: float = 0.0
    language: str = "en"


class ASREngine(ABC):
    """
    Abstract base class for streaming speech recognition engines.
    """

    @abstractmethod
    async def start(self) -> None:
        """Initialize the engine and open connections."""
        ...

    @abstractmethod
    async def push_audio(self, pcm_data: bytes) -> None:
        """Push raw PCM16 bytes into the engine."""
        ...

    @abstractmethod
    async def end_of_speech(self) -> None:
        """Signal that the current utterance has ended (forces finalization)."""
        ...

    @abstractmethod
    async def receive_transcripts(self) -> AsyncIterator[TranscriptResult]:
        """Async generator yielding TranscriptResult objects as they arrive."""
        yield TranscriptResult(text="", is_final=True) # type hint generator

    @abstractmethod
    async def stop(self) -> None:
        """Close connections and cleanup."""
        ...
