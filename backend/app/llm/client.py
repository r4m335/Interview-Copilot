"""
LLM client with fallback chain: Ollama → OpenRouter → Groq.

All providers use OpenAI-compatible APIs (via the `openai` Python package).
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.llm.base import LLMBase

logger = logging.getLogger(__name__)


class OpenAICompatibleLLM(LLMBase):
    """LLM client that works with any OpenAI-compatible API endpoint."""

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
    ) -> None:
        self.name = name
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )
        return self._client

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def generate(self, prompt: str, system_prompt: str) -> str:
        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
                stream=False,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"[{self.name}] Generation error: {e}")
            raise

    async def stream(self, prompt: str, system_prompt: str) -> AsyncIterator[str]:
        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
                stream=True,
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"[{self.name}] Streaming error: {e}")
            raise


class FallbackLLMClient:
    """
    LLM client with automatic fallback chain.

    Priority: Ollama → OpenRouter → Groq
    If the primary fails, automatically tries the next provider.
    """

    def __init__(self) -> None:
        self._providers: list[OpenAICompatibleLLM] = []
        self._setup_providers()

    def _setup_providers(self) -> None:
        """Initialize providers in priority order."""
        # 1. Ollama (primary)
        if settings.ollama_api_key:
            self._providers.append(
                OpenAICompatibleLLM(
                    name="Ollama",
                    api_key=settings.ollama_api_key,
                    base_url=settings.ollama_url.replace("/api/generate", "/v1"),
                    model=settings.ollama_model,
                )
            )

        # 2. OpenRouter (fallback)
        if settings.openrouter_api_key:
            self._providers.append(
                OpenAICompatibleLLM(
                    name="OpenRouter",
                    api_key=settings.openrouter_api_key,
                    base_url="https://openrouter.ai/api/v1",
                    model=settings.openrouter_model,
                )
            )

        # 3. Groq (fallback)
        if settings.groq_api_key:
            self._providers.append(
                OpenAICompatibleLLM(
                    name="Groq",
                    api_key=settings.groq_api_key,
                    base_url="https://api.groq.com/openai/v1",
                    model=settings.groq_model,
                )
            )

        if not self._providers:
            logger.warning("No LLM providers configured!")

    async def generate(self, prompt: str, system_prompt: str) -> str:
        """Try each provider in order until one succeeds."""
        last_error: Exception | None = None

        for provider in self._providers:
            if not provider.is_available():
                continue
            try:
                logger.info(f"Trying LLM provider: {provider.name}")
                result = await provider.generate(prompt, system_prompt)
                logger.info(f"LLM response from {provider.name}")
                return result
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed: {e}")
                last_error = e
                continue

        raise RuntimeError(
            f"All LLM providers failed. Last error: {last_error}"
        )

    async def stream(self, prompt: str, system_prompt: str) -> AsyncIterator[str]:
        """Try each provider in order until one streams successfully."""
        last_error: Exception | None = None

        for provider in self._providers:
            if not provider.is_available():
                continue
            try:
                logger.info(f"Trying streaming from: {provider.name}")
                async for token in provider.stream(prompt, system_prompt):
                    yield token
                return  # Success — stop trying other providers
            except Exception as e:
                logger.warning(f"Streaming from {provider.name} failed: {e}")
                last_error = e
                continue

        raise RuntimeError(
            f"All LLM providers failed for streaming. Last error: {last_error}"
        )


# Singleton
llm_client = FallbackLLMClient()
