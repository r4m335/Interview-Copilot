"""Abstract LLM interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMBase(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str) -> str:
        """Generate a complete response."""
        ...

    @abstractmethod
    async def stream(self, prompt: str, system_prompt: str) -> AsyncIterator[str]:
        """Stream response tokens one at a time."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and reachable."""
        ...
