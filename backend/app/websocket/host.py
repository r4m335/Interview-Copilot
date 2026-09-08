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

from app.asr.fallback_engine import FallbackASREngine
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
CONTROL_MARKER = 0xFFFFFFFF


@router.websocket("/ws/host/{session_id}")
async def host_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for the Chrome extension (host).
    """
    session = session_manager.get_session(session_id)
    if session is None:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()
    session.host_ws = websocket
    logger.info(f"Host connected to session {session_id}")

    answer_cache = AnswerCache()

    # Load ASR model
    await websocket.send_json(
        StatusMessage(state=StatusState.PROCESSING, detail="Connecting ASR model...", tab_title=session.tab_title).model_dump()
    )
    
    asr_engine = FallbackASREngine(gemini_api_key=settings.gemini_api_key)
    try:
        await asr_engine.start()
        
        await websocket.send_json(
            StatusMessage(state=StatusState.LISTENING, detail="ASR ready", tab_title=session.tab_title).model_dump()
        )
        await session.broadcast_to_viewers(
            StatusMessage(state=StatusState.LISTENING, detail="Host connected", tab_title=session.tab_title).model_dump()
        )
    except Exception as e:
        logger.error(f"ASR engine start failed: {e}")
        await websocket.send_json(
            StatusMessage(state=StatusState.ERROR, detail=f"ASR start failed: {e}").model_dump()
        )
        await websocket.close()
        return

    # Question handler
    async def on_question_ready(question: str) -> None:
        logger.info(f"======== DETECTED QUESTION ========\n{question}\n===================================")

        score = score_question(question)
        if score < settings.heuristic_score_threshold:
            logger.info(f"Question score too low ({score:.2f}): {question[:50]}...")
            return

        await session.broadcast_to_viewers(
            QuestionMessage(text=question).model_dump()
        )

        cached = answer_cache.get(question)
        if cached:
            await session.broadcast_to_viewers(AnswerStartMessage(question=question).model_dump())
            await session.broadcast_to_viewers(AnswerDeltaMessage(text=cached).model_dump())
            await session.broadcast_to_viewers(AnswerCompleteMessage(question=question, full_text=cached).model_dump())
            return

        await session.broadcast_to_viewers(AnswerStartMessage(question=question).model_dump())
        await session.broadcast_to_viewers(StatusMessage(state=StatusState.GENERATING, detail="Generating answer...").model_dump())

        full_answer = ""
        try:
            async for token in generate_answer_stream(question):
                full_answer += token
                await session.broadcast_to_viewers(AnswerDeltaMessage(text=token).model_dump())

            if full_answer:
                answer_cache.put(question, full_answer)
                session.last_question = question
                session.last_answer = full_answer
                await session.broadcast_to_viewers(AnswerCompleteMessage(question=question, full_text=full_answer).model_dump())

            await session.broadcast_to_viewers(StatusMessage(state=StatusState.LISTENING, detail="Listening...").model_dump())
        except Exception as e:
            logger.error(f"LLM error: {e}")
            await session.broadcast_to_viewers(StatusMessage(state=StatusState.ERROR, detail=f"LLM error: {e}").model_dump())

    segmenter = QuestionSegmenter(on_question=on_question_ready)

    # Background task to receive transcripts from the engine
    async def transcript_consumer_loop() -> None:
        try:
            async for result in asr_engine.receive_transcripts():
                if not result or not result.text.strip():
                    continue
                    
                logger.info(f"ASR Transcript (Final={result.is_final}): {result.text}")
                status = TranscriptStatus.FINAL if result.is_final else TranscriptStatus.PARTIAL
                
                msg = TranscriptMessage(
                    status=status,
                    text=result.text,
                    timestamp=time.time(),
                )
                
                await websocket.send_json(msg.model_dump())
                await session.broadcast_to_viewers(msg.model_dump())

                if result.is_final:
                    await segmenter.on_final_transcript(result.text)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Transcript consumer error: {e}")

    consumer_task = asyncio.create_task(transcript_consumer_loop())

    try:
        while True:
            data = await websocket.receive_bytes()

            if len(data) <= HEADER_SIZE:
                continue

            # Parse header
            seq_num, timestamp = struct.unpack("<II", data[:HEADER_SIZE])
            payload = data[HEADER_SIZE:]

            if seq_num == CONTROL_MARKER:
                try:
                    control_cmd = payload.decode('utf-8')
                    if control_cmd == "speech_end":
                        await asr_engine.end_of_speech()
                except Exception as e:
                    logger.error(f"Error handling control frame: {e}")
                continue

            # Push audio to engine
            await asr_engine.push_audio(payload)

    except WebSocketDisconnect:
        logger.info(f"Host disconnected from session {session_id}")
    except Exception as e:
        logger.error(f"Host WebSocket error: {e}")
    finally:
        consumer_task.cancel()
        await asr_engine.stop()
        segmenter.reset()
        session.host_ws = None
        
        try:
            await session.broadcast_to_viewers(
                StatusMessage(state=StatusState.IDLE, detail="Host disconnected", tab_title=session.tab_title).model_dump()
            )
        except Exception:
            pass
        logger.info(f"Host cleanup complete for session {session_id}")
