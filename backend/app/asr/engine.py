"""Abstract ASR engine interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

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
    Abstract base class for speech recognition engines.

    Implementations must provide:
    - load_model(): Initialize the model
    - transcribe(): Process audio and return transcript
    - reset(): Clear internal state for a new utterance
    """

    @abstractmethod
    def load_model(self) -> None:
        """Load the ASR model into memory."""
        ...

    @abstractmethod
    def transcribe(self, audio: np.ndarray) -> Optional[TranscriptResult]:
        """
        Transcribe audio data.

        Args:
            audio: Float32 numpy array of audio samples (16kHz mono).

        Returns:
            TranscriptResult or None if no speech detected.
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset internal state for a new utterance."""
        ...
