"""
Question segmenter — waits for silence boundary before finalizing.

Prevents generating six answers for one long question. Accumulates
transcript fragments and only emits a "question ready" event after
300-700ms of silence following a final ASR transcript.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Awaitable, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class QuestionSegmenter:
    """
    Accumulates final transcripts and emits a complete question
    after a silence boundary.

    Usage:
        segmenter = QuestionSegmenter(on_question=my_callback)
        await segmenter.on_final_transcript("What is", timestamp)
        await segmenter.on_final_transcript("What is polymorphism?", timestamp)
        # ... after 500ms silence ...
        # my_callback("What is polymorphism?") is called
    """

    def __init__(
        self,
        on_question: Callable[[str], Awaitable[None]],
        silence_threshold_ms: int | None = None,
    ) -> None:
        self._on_question = on_question
        self._silence_ms = silence_threshold_ms or settings.silence_threshold_ms
        self._pending_text: str = ""
        self._last_update_time: float = 0.0
        self._timer_task: Optional[asyncio.Task] = None

    async def on_final_transcript(self, text: str, timestamp: float | None = None) -> None:
        """
        Called when ASR emits a final transcript.

        Resets the silence timer. The question is only emitted
        once silence_threshold_ms passes with no new transcript.
        """
        text = text.strip()
        if not text:
            return

        self._pending_text = text
        self._last_update_time = timestamp or time.time()

        # Cancel existing timer
        if self._timer_task is not None and not self._timer_task.done():
            self._timer_task.cancel()

        # Start new silence timer
        self._timer_task = asyncio.create_task(self._silence_timer())

    async def _silence_timer(self) -> None:
        """Wait for silence threshold, then emit the question."""
        try:
            await asyncio.sleep(self._silence_ms / 1000.0)

            # Timer expired — no new speech arrived
            if self._pending_text:
                question = self._pending_text
                self._pending_text = ""
                logger.info(f"Question finalized: {question}")
                await self._on_question(question)

        except asyncio.CancelledError:
            # Timer was cancelled because new speech arrived — normal
            pass

    def reset(self) -> None:
        """Reset state."""
        self._pending_text = ""
        self._last_update_time = 0.0
        if self._timer_task is not None and not self._timer_task.done():
            self._timer_task.cancel()
            self._timer_task = None
