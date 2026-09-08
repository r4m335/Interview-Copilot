"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)


class Settings(BaseSettings):
    """Central configuration for the interview copilot backend."""

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- ASR ---
    asr_engine: str = "faster_whisper"
    asr_model: str = "large-v3-turbo"

    # --- LLM providers (priority: ollama → openrouter → groq) ---
    # Ollama
    ollama_url: str = "https://ollama.com/api/generate"
    ollama_api_key: str = ""
    ollama_model: str = "gpt-oss:20b"

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemma-3-27b-it:free"

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-70b-versatile"

    # Additional (available but not primary)
    gemini_api_key: str = ""
    openai_api_key: str = ""

    # --- Session ---
    session_expiry_minutes: int = 30
    session_id_length: int = 6

    # --- Audio ---
    sample_rate: int = 16000
    channels: int = 1
    audio_buffer_seconds: float = 2.0

    # --- Question detection ---
    silence_threshold_ms: int = 500
    heuristic_score_threshold: float = 0.3

    # --- LLM ---
    llm_max_tokens: int = 500
    llm_temperature: float = 0.3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
