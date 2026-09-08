import asyncio
import logging
from typing import AsyncIterator

from google import genai
from google.genai import types

from app.asr.engine import ASREngine, TranscriptResult

logger = logging.getLogger(__name__)

class GeminiLiveEngine(ASREngine):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        self.session = None
        self.receive_task = None
        self.transcript_queue = asyncio.Queue()
        self._is_running = False
        self.current_text = ""
        self.committed_text = ""

    async def start(self) -> None:
        if self._is_running:
            return

        logger.info("Connecting to Gemini 3.5 Transcribe Live...")
        
        # Configure Live API for transcription
        config = types.LiveConnectConfig(
            response_modalities=["TEXT"],
            input_audio_transcription=types.AudioTranscriptionConfig(
                language_codes=["en-US"],
                custom_vocabulary=[
                    "polymorphism", "encapsulation", "inheritance", "abstraction", 
                    "algorithm", "recursion", "Kubernetes", "TypeScript", 
                    "JavaScript", "PostgreSQL", "MongoDB", "Redis", 
                    "Dijkstra", "binary search", "hash table", "linked list", "dynamic programming"
                ]
            )
        )

        self._connect_cm = self.client.aio.live.connect(
            model='gemini-3.5-transcribe-live',
            config=config
        )
        self.session = await self._connect_cm.__aenter__()
        
        self._is_running = True
        self.current_text = ""
        self.committed_text = ""
        self.receive_task = asyncio.create_task(self._receive_loop())
        logger.info("Gemini Live connection established.")

    async def push_audio(self, pcm_data: bytes) -> None:
        if not self._is_running or not self.session:
            return
            
        try:
            # Send raw PCM16 audio
            await self.session.send(
                input={"data": pcm_data, "mime_type": "audio/pcm;rate=16000"}
            )
        except Exception as e:
            logger.error(f"Gemini push_audio error: {e}")
            await self.stop()
            raise e

    async def end_of_speech(self) -> None:
        if not self._is_running or not self.session:
            return
            
        logger.info("Gemini Live: end of speech signaled by Chrome VAD.")
        try:
            await self.session.send(end_of_turn=True)
            # Force local finalization if we have text
            if self.current_text:
                await self.transcript_queue.put(
                    TranscriptResult(text=self.current_text, is_final=True)
                )
                
                # Commit the text so we can subtract it from future interim transcripts
                if self.committed_text:
                    self.committed_text += " " + self.current_text
                else:
                    self.committed_text = self.current_text
                
                self.current_text = ""
        except Exception as e:
            logger.error(f"Gemini end_of_speech error: {e}")

    async def _receive_loop(self) -> None:
        try:
            async for response in self.session.receive():
                if not self._is_running:
                    break
                    
                if hasattr(response, 'server_content') and response.server_content:
                    content = response.server_content
                    logger.info(f"Gemini Live Response: {content}")
                    
                    text = ""
                    is_final = False
                    
                    if hasattr(content, 'input_transcription') and content.input_transcription:
                        text = getattr(content.input_transcription, 'text', "")
                        is_final = getattr(content.input_transcription, 'is_final', False)
                    elif hasattr(content, 'interim_input_transcription') and content.interim_input_transcription:
                        text = getattr(content.interim_input_transcription, 'text', "")
                        # interim transcripts are typically not final
                        is_final = False
                    elif hasattr(content, 'model_turn') and content.model_turn:
                        if hasattr(content.model_turn, 'parts') and content.model_turn.parts:
                            text = getattr(content.model_turn.parts[0], 'text', "")
                            
                    turn_complete = getattr(response, 'turn_complete', False)
                    if turn_complete:
                        is_final = True
                            
                    if text:
                        # Diff against committed text to prevent accumulation
                        text = text.strip()
                        
                        # Sometimes Gemini corrects words slightly, so we look for the last few words
                        # of the committed text to find the cut-off point.
                        if self.committed_text:
                            # Exact prefix match
                            if text.startswith(self.committed_text):
                                text = text[len(self.committed_text):].strip()
                            else:
                                # Try to find suffix of committed text
                                suffix = self.committed_text[-20:] if len(self.committed_text) > 20 else self.committed_text
                                idx = text.rfind(suffix)
                                if idx != -1:
                                    text = text[idx + len(suffix):].strip()

                        self.current_text = text
                        
                    if is_final and self.current_text:
                        await self.transcript_queue.put(
                            TranscriptResult(text=self.current_text, is_final=True)
                        )
                        
                        if self.committed_text:
                            self.committed_text += " " + self.current_text
                        else:
                            self.committed_text = self.current_text
                            
                        self.current_text = ""
                    elif text:
                        await self.transcript_queue.put(
                            TranscriptResult(text=self.current_text, is_final=False)
                        )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Gemini receive loop error: {e}")
            # Put error in queue to propagate failure
            await self.transcript_queue.put(e)
            await self.stop()
        finally:
            logger.info("Gemini Live receive loop terminated.")

    async def receive_transcripts(self) -> AsyncIterator[TranscriptResult]:
        while self._is_running or not self.transcript_queue.empty():
            try:
                item = await asyncio.wait_for(self.transcript_queue.get(), timeout=1.0)
                if isinstance(item, Exception):
                    raise item
                yield item
            except asyncio.TimeoutError:
                continue

    async def stop(self) -> None:
        if not self._is_running:
            return
            
        self._is_running = False
        if self.receive_task:
            self.receive_task.cancel()
            
        if self.session and hasattr(self, '_connect_cm'):
            try:
                await self._connect_cm.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing Gemini Live session: {e}")
        
        self.session = None
        logger.info("Gemini Live connection closed.")
