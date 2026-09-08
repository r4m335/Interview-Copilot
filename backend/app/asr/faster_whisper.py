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

import asyncio
import logging
import time
from typing import Optional, AsyncIterator

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
        from app.audio.buffer import AudioBuffer
        self._model = None
        self._previous_text: str = ""
        self._last_transcribe_time: float = 0.0
        self._min_interval: float = 1.0
        
        self.audio_buffer = AudioBuffer(max_seconds=30.0)
        self.transcript_queue = asyncio.Queue()
        self._is_running = False
        self.transcribe_task = None
        self._last_speech_time = 0.0

    async def start(self) -> None:
        if self._is_running:
            return

        try:
            from faster_whisper import WhisperModel
            model_size = settings.asr_model
            logger.info(f"Loading faster-whisper model: {model_size}")

            # Note: in a real app, loading a large model should probably happen in a thread pool
            self._model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
            )
            logger.info(f"faster-whisper model loaded: {model_size}")
            
            self._is_running = True
            self.transcribe_task = asyncio.create_task(self._transcribe_loop())
        except Exception as e:
            logger.error(f"Failed to load faster-whisper model: {e}")
            raise e

    async def push_audio(self, pcm_data: bytes) -> None:
        if not self._is_running:
            return
        self.audio_buffer.add_pcm16(pcm_data)

    async def end_of_speech(self) -> None:
        """Force finalization of the current buffer."""
        if not self._is_running or not self._previous_text:
            return
            
        await self.transcript_queue.put(
            TranscriptResult(text=self._previous_text, is_final=True)
        )
        self._previous_text = ""
        self.audio_buffer.clear()

    async def _transcribe_loop(self) -> None:
        """Continuously transcribe accumulated audio."""
        self._last_speech_time = time.time()
        
        while self._is_running:
            await asyncio.sleep(0.5)

            audio = self.audio_buffer.get_audio(last_seconds=settings.audio_buffer_seconds)
            if len(audio) == 0:
                continue

            # Throttle
            now = time.time()
            if now - self._last_transcribe_time < self._min_interval:
                continue

            self._last_transcribe_time = now

            try:
                # Run faster-whisper blocking call in thread
                segments, info = await asyncio.to_thread(
                    self._model.transcribe,
                    audio,
                    language="en",
                    beam_size=1,
                    best_of=1,
                    temperature=0.0,
                    vad_filter=False,
                    vad_parameters=dict(min_silence_duration_ms=300, speech_pad_ms=200)
                )

                full_text = " ".join([s.text.strip() for s in segments if s.text.strip()]).strip()

                if not full_text or full_text == self._previous_text:
                    # No new speech. Check silence fallback (in case frontend VAD missed it)
                    if time.time() - self._last_speech_time > 1.5 and self._previous_text:
                        await self.transcript_queue.put(
                            TranscriptResult(text=self._previous_text, is_final=True)
                        )
                        self._previous_text = ""
                        self.audio_buffer.clear()
                        self._last_speech_time = time.time()
                    continue

                self._previous_text = full_text
                self._last_speech_time = time.time()
                
                await self.transcript_queue.put(
                    TranscriptResult(text=full_text, is_final=False)
                )

            except Exception as e:
                logger.error(f"Whisper transcription error: {e}")

    async def receive_transcripts(self) -> AsyncIterator[TranscriptResult]:
        while self._is_running or not self.transcript_queue.empty():
            try:
                yield await asyncio.wait_for(self.transcript_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

    async def stop(self) -> None:
        self._is_running = False
        if self.transcribe_task:
            self.transcribe_task.cancel()
        self.audio_buffer.clear()

