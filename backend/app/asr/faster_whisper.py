"""
Faster-whisper ASR engine — pseudo-streaming via rolling buffer.

Strategy:
  1. Audio chunks arrive and accumulate in a buffer.
  2. Every ~1-2 seconds of new audio, run faster-whisper on the
     accumulated buffer.
  3. Diff against previous transcription to produce partials.
  4. On silence (no new audio for threshold), emit final.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np

from app.asr.engine import ASREngine, TranscriptResult
from app.config import settings

logger = logging.getLogger(__name__)


class FasterWhisperEngine(ASREngine):
    """
    ASR engine using faster-whisper (CTranslate2).

    Provides pseudo-streaming by re-transcribing the growing audio
    buffer and diffing against the previous result.
    """

    def __init__(self) -> None:
        self._model = None
        self._previous_text: str = ""
        self._last_transcribe_time: float = 0.0
        self._min_interval: float = 1.0  # Min seconds between transcriptions

    def load_model(self) -> None:
        """Load the faster-whisper model."""
        try:
            from faster_whisper import WhisperModel

            model_size = settings.asr_model
            logger.info(f"Loading faster-whisper model: {model_size}")

            self._model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
            )

            logger.info(f"faster-whisper model loaded: {model_size}")
        except ImportError:
            logger.error(
                "faster-whisper not installed. "
                "Install with: pip install faster-whisper"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to load faster-whisper model: {e}")
            raise

    def transcribe(self, audio: np.ndarray) -> Optional[TranscriptResult]:
        """
        Transcribe the given audio buffer.

        Uses a minimum interval to avoid transcribing too frequently.
        Returns partial results (diffed against previous), or None
        if not enough time has passed or no speech detected.
        """
        if self._model is None:
            logger.error("Model not loaded — call load_model() first")
            return None

        if len(audio) == 0:
            return None

        # Throttle: don't transcribe more often than _min_interval
        now = time.time()
        if now - self._last_transcribe_time < self._min_interval:
            return None

        self._last_transcribe_time = now

        try:
            segments, info = self._model.transcribe(
                audio,
                language="en",
                beam_size=1,  # Faster, lower quality — good for streaming
                best_of=1,
                temperature=0.0,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=300,
                    speech_pad_ms=200,
                ),
            )

            # Collect all segment texts
            full_text = ""
            for segment in segments:
                full_text += segment.text

            full_text = full_text.strip()

            if not full_text:
                return None

            # Determine if this is new content
            is_new = full_text != self._previous_text
            if not is_new:
                return None

            self._previous_text = full_text

            return TranscriptResult(
                text=full_text,
                is_final=False,  # Caller decides finality via silence detection
                confidence=getattr(info, "language_probability", 0.0),
                language=getattr(info, "language", "en"),
            )

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None

    def finalize(self) -> Optional[TranscriptResult]:
        """
        Mark the current transcript as final and return it.

        Called when silence is detected (no new audio for a threshold).
        """
        if not self._previous_text:
            return None

        result = TranscriptResult(
            text=self._previous_text,
            is_final=True,
        )
        self._previous_text = ""
        return result

    def reset(self) -> None:
        """Reset state for a new utterance."""
        self._previous_text = ""
        self._last_transcribe_time = 0.0
