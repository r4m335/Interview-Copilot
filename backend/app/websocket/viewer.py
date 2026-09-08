"""
WebSocket endpoint for the viewer (phone browser).

Read-only connection — receives transcripts, questions, and
streaming answers from the backend. No audio sent from viewer.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.models.schemas import StatusMessage, StatusState
from app.sessions.manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/viewer/{session_id}")
async def viewer_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for the phone viewer.

    Protocol:
    - Backend sends JSON messages (transcripts, questions, answer deltas)
    - Viewer sends nothing (read-only)
    """
    session = session_manager.get_session(session_id)
    if session is None:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()
    session.viewer_ws_list.append(websocket)
    logger.info(f"Viewer connected to session {session_id}")

    # Send current status
    try:
        await websocket.send_json(
            StatusMessage(
                state=StatusState.LISTENING if session.host_ws else StatusState.IDLE,
                detail="Connected" if session.host_ws else "Waiting for host...",
                tab_title=session.tab_title if session.host_ws else None
            ).model_dump()
        )

        # Send last question/answer if available (for late-joining viewers)
        if session.last_question:
            from app.models.schemas import QuestionMessage, AnswerCompleteMessage

            await websocket.send_json(
                QuestionMessage(text=session.last_question).model_dump()
            )
            if session.last_answer:
                await websocket.send_json(
                    AnswerCompleteMessage(
                        question=session.last_question,
                        full_text=session.last_answer,
                    ).model_dump()
                )
    except Exception as e:
        logger.error(f"Error sending initial state to viewer: {e}")

    # Keep connection alive — viewer doesn't send data,
    # but we need to detect disconnects
    try:
        while True:
            # Wait for any message (ping/pong or disconnect)
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"Viewer disconnected from session {session_id}")
    except Exception as e:
        logger.error(f"Viewer WebSocket error: {e}")
    finally:
        if websocket in session.viewer_ws_list:
            session.viewer_ws_list.remove(websocket)
        logger.info(f"Viewer cleanup complete for session {session_id}")
