"""Stub for server-side VAD — not used in V1 (extension handles VAD)."""

from __future__ import annotations


class ServerVAD:
    """
    Placeholder for server-side Voice Activity Detection.

    In V1, all VAD is done in the Chrome extension's AudioWorklet.
    This stub exists so the import path is ready when we add
    server-side Silero VAD as a safety layer in V2.
    """

    def __init__(self) -> None:
        self.enabled = False

    def is_speech(self, audio_chunk: bytes) -> bool:
        """Always returns True — no server-side filtering in V1."""
        return True
