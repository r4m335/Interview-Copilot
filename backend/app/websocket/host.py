"""
WebSocket endpoint for the host (Chrome extension).

Receives binary PCM audio frames, feeds them to ASR,
runs the question detection + LLM pipeline,
and pushes results to connected viewers.
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.asr.faster_whisper import FasterWhisperEngine
from app.audio.buffer import AudioBuffer
from app.config import settings
from app.llm.cache import AnswerCache
from app.llm.streaming import generate_answer_stream, IGNORE_SENTINEL
from app.models.schemas import (
    AnswerCompleteMessage,
    AnswerDeltaMessage,
    AnswerStartMessage,
    QuestionMessage,
    StatusMessage,
    StatusState,
    TranscriptMessage,
    TranscriptStatus,
)
from app.questions.detector import score_question
from app.questions.segmenter import QuestionSegmenter
from app.sessions.manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Header format: 4-byte sequence number + 4-byte timestamp (both uint32 LE)
HEADER_SIZE = 8


@router.websocket("/ws/host/{session_id}")
async def host_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for the Chrome extension (host).

    Protocol:
    - Extension sends binary frames: [4B seq][4B timestamp][PCM16 bytes]
    - Backend sends JSON status/transcript messages back to host
    """
    session = session_manager.get_session(session_id)
    if session is None:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()
    session.host_ws = websocket
    logger.info(f"Host connected to session {session_id}")

    # Initialize per-session components
    audio_buffer = AudioBuffer(max_seconds=30.0)
    asr_engine = FasterWhisperEngine()
    answer_cache = AnswerCache()

    # Load ASR model
    try:
        await websocket.send_json(
            StatusMessage(state=StatusState.PROCESSING, detail="Loading ASR model...").model_dump()
        )
        asr_engine.load_model()
        await websocket.send_json(
            StatusMessage(state=StatusState.LISTENING, detail="ASR ready").model_dump()
        )
    except Exception as e:
        logger.error(f"ASR model load failed: {e}")
        await websocket.send_json(
            StatusMessage(state=StatusState.ERROR, detail=f"ASR load failed: {e}").model_dump()
        )
        await websocket.close()
        return

    # Question handler — called when segmenter finalizes a question
    async def on_question_ready(question: str) -> None:
        """Process a finalized question through the LLM pipeline."""
        logger.info(f"Question ready: {question}")

        # Check heuristic score
        score = score_question(question)
        if score < settings.heuristic_score_threshold:
            logger.info(f"Question score too low ({score:.2f}): {question[:50]}...")
            return

        # Notify viewers about the question
        await session.broadcast_to_viewers(
            QuestionMessage(text=question).model_dump()
        )

        # Check cache
        cached = answer_cache.get(question)
        if cached:
            await session.broadcast_to_viewers(
                AnswerStartMessage(question=question).model_dump()
            )
            await session.broadcast_to_viewers(
                AnswerDeltaMessage(text=cached).model_dump()
            )
            await session.broadcast_to_viewers(
                AnswerCompleteMessage(question=question, full_text=cached).model_dump()
            )
            return

        # Stream answer from LLM
        await session.broadcast_to_viewers(
            AnswerStartMessage(question=question).model_dump()
        )
        await session.broadcast_to_viewers(
            StatusMessage(state=StatusState.GENERATING, detail="Generating answer...").model_dump()
        )

        full_answer = ""
        try:
            async for token in generate_answer_stream(question):
                full_answer += token
                await session.broadcast_to_viewers(
                    AnswerDeltaMessage(text=token).model_dump()
                )

            if full_answer:
                # Cache the answer
                answer_cache.put(question, full_answer)
                session.last_question = question
                session.last_answer = full_answer

                await session.broadcast_to_viewers(
                    AnswerCompleteMessage(
                        question=question, full_text=full_answer
                    ).model_dump()
                )

            await session.broadcast_to_viewers(
                StatusMessage(state=StatusState.LISTENING, detail="Listening...").model_dump()
            )

        except Exception as e:
            logger.error(f"LLM error: {e}")
            await session.broadcast_to_viewers(
                StatusMessage(state=StatusState.ERROR, detail=f"LLM error: {e}").model_dump()
            )

    segmenter = QuestionSegmenter(on_question=on_question_ready)

    # Background task: periodically run ASR on the buffer
    async def asr_loop() -> None:
        """Continuously transcribe accumulated audio."""
        last_speech_time = time.time()

        while True:
            await asyncio.sleep(0.5)  # Check every 500ms

            audio = audio_buffer.get_audio(last_seconds=settings.audio_buffer_seconds)
            if len(audio) == 0:
                # Check for silence → finalize ASR
                if time.time() - last_speech_time > 1.5:
                    result = asr_engine.finalize()
                    if result and result.text.strip():
                        msg = TranscriptMessage(
                            status=TranscriptStatus.FINAL,
                            text=result.text,
                            timestamp=time.time(),
                        )
                        await websocket.send_json(msg.model_dump())
                        await session.broadcast_to_viewers(msg.model_dump())
                        await segmenter.on_final_transcript(result.text)
                continue

            last_speech_time = time.time()
            result = asr_engine.transcribe(audio)

            if result and result.text.strip():
                status = TranscriptStatus.FINAL if result.is_final else TranscriptStatus.PARTIAL
                msg = TranscriptMessage(
                    status=status,
                    text=result.text,
                    timestamp=time.time(),
                )
                # Send to host (for status display)
                await websocket.send_json(msg.model_dump())
                # Send to viewers
                await session.broadcast_to_viewers(msg.model_dump())

                if result.is_final:
                    await segmenter.on_final_transcript(result.text)

    asr_task = asyncio.create_task(asr_loop())

    try:
        while True:
            data = await websocket.receive_bytes()

            if len(data) <= HEADER_SIZE:
                continue

            # Parse header
            seq_num, timestamp = struct.unpack("<II", data[:HEADER_SIZE])
            pcm_data = data[HEADER_SIZE:]

            # Add to buffer
            n_samples = audio_buffer.add_pcm16(pcm_data)

            # Log periodically (not every frame)
            if seq_num % 100 == 0:
                logger.debug(
                    f"Audio received: {n_samples} samples, "
                    f"seq={seq_num}, buffer={audio_buffer.duration_seconds:.1f}s"
                )

    except WebSocketDisconnect:
        logger.info(f"Host disconnected from session {session_id}")
    except Exception as e:
        logger.error(f"Host WebSocket error: {e}")
    finally:
        asr_task.cancel()
        segmenter.reset()
        session.host_ws = None
        logger.info(f"Host cleanup complete for session {session_id}")
