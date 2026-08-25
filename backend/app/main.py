"""
FastAPI application — main entry point.

Routes:
  POST   /api/session         → Create session
  GET    /api/session/{id}    → Session info
  DELETE /api/session/{id}    → End session
  WS     /ws/host/{id}        → Extension audio stream
  WS     /ws/viewer/{id}      → Phone viewer stream
  GET    /session/{id}        → Serve mobile client (later)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models.schemas import SessionCreate, SessionInfo
from app.sessions.manager import session_manager
from app.websocket.host import router as host_router
from app.websocket.viewer import router as viewer_router

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Interview Copilot backend starting...")
    session_manager.start_cleanup_loop()
    logger.info(f"Server ready on {settings.host}:{settings.port}")
    yield
    session_manager.stop_cleanup_loop()
    logger.info("Backend shutdown complete")


app = FastAPI(
    title="Interview Copilot",
    description="Real-time programming interview assistant",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow extension and mobile client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket routes
app.include_router(host_router)
app.include_router(viewer_router)


# --- REST API ---


@app.post("/api/session", response_model=SessionCreate)
async def create_session():
    """Create a new interview session."""
    session = session_manager.create_session()
    logger.info(f"Session created: {session.session_id}")
    return SessionCreate(
        session_id=session.session_id,
        host_token=session.host_token,
        viewer_token=session.viewer_token,
    )


@app.get("/api/session/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    """Get session info."""
    session = session_manager.get_session(session_id)
    if session is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Session not found")
    return SessionInfo(
        session_id=session.session_id,
        created_at=session.created_at,
        expires_at=session.expires_at,
        is_active=session.is_active,
    )


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """End a session."""
    deleted = session_manager.delete_session(session_id)
    if not deleted:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Session not found")
    logger.info(f"Session deleted: {session_id}")
    return {"status": "deleted", "session_id": session_id}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


# --- Entry point ---

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
