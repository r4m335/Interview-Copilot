import asyncio
import logging
from typing import AsyncIterator, Optional

from app.asr.engine import ASREngine, TranscriptResult
from app.asr.faster_whisper import FasterWhisperEngine
from app.asr.gemini_live import GeminiLiveEngine

logger = logging.getLogger(__name__)

class FallbackASREngine(ASREngine):
    def __init__(self, gemini_api_key: Optional[str] = None):
        self.gemini_api_key = gemini_api_key
        self.active_engine = None
        self._is_running = False
        self._engine_switch_lock = asyncio.Lock()
        
    async def _init_gemini_with_retries(self):
        retries = 0
        max_retries = 3
        backoff = 1.0
        
        while retries < max_retries:
            try:
                engine = GeminiLiveEngine(api_key=self.gemini_api_key)
                await engine.start()
                return engine
            except Exception as e:
                retries += 1
                logger.error(f"Gemini Live connection failed (Attempt {retries}/{max_retries}): {e}")
                if retries < max_retries:
                    await asyncio.sleep(backoff)
                    backoff *= 2
        
        logger.warning("All Gemini Live connection attempts failed. Falling back to Whisper.")
        return None

    async def start(self) -> None:
        if self._is_running:
            return
            
        self._is_running = True
        
        if self.gemini_api_key:
            self.active_engine = await self._init_gemini_with_retries()
            
        if not self.active_engine:
            logger.info("Initializing fallback FasterWhisperEngine...")
            self.active_engine = FasterWhisperEngine()
            await self.active_engine.start()

    async def _handle_engine_failure(self):
        """Called when active engine fails during streaming."""
        async with self._engine_switch_lock:
            # If already switched to Whisper, nothing to do
            if isinstance(self.active_engine, FasterWhisperEngine):
                return
                
            logger.warning("Gemini Live Engine failed mid-session! Initiating fallback recovery...")
            try:
                await self.active_engine.stop()
            except:
                pass
                
            # Attempt to restart Gemini up to 3 times
            new_engine = await self._init_gemini_with_retries()
            
            if not new_engine:
                logger.warning("Gemini Live recovery failed. Permanently switching to FasterWhisperEngine.")
                new_engine = FasterWhisperEngine()
                await new_engine.start()
                
            self.active_engine = new_engine
            logger.info(f"Fallback recovery complete. Active engine is now {self.active_engine.__class__.__name__}")

    async def push_audio(self, pcm_data: bytes) -> None:
        if not self._is_running or not self.active_engine:
            return
            
        try:
            await self.active_engine.push_audio(pcm_data)
        except Exception as e:
            logger.error(f"Error pushing audio: {e}")
            asyncio.create_task(self._handle_engine_failure())

    async def end_of_speech(self) -> None:
        if not self._is_running or not self.active_engine:
            return
            
        try:
            await self.active_engine.end_of_speech()
        except Exception as e:
            logger.error(f"Error signaling end of speech: {e}")
            asyncio.create_task(self._handle_engine_failure())

    async def receive_transcripts(self) -> AsyncIterator[TranscriptResult]:
        while self._is_running:
            if not self.active_engine:
                await asyncio.sleep(0.5)
                continue
                
            try:
                # Iterate over the active engine's transcripts
                # If engine fails/swaps, this iteration breaks and we restart the loop
                async for transcript in self.active_engine.receive_transcripts():
                    if not self._is_running:
                        break
                    yield transcript
            except Exception as e:
                logger.error(f"Error receiving transcripts: {e}")
                await self._handle_engine_failure()

    async def stop(self) -> None:
        self._is_running = False
        if self.active_engine:
            await self.active_engine.stop()
            self.active_engine = None
