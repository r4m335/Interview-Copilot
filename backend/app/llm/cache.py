"""
In-memory LRU answer cache — per-session, no database required.

If the interviewer asks "What is polymorphism?" and later asks
"Can you explain polymorphism?", the normalized hash will match
and the cached answer is returned instantly.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Optional

from app.questions.normalizer import question_hash

logger = logging.getLogger(__name__)


class AnswerCache:
    """
    Simple LRU cache for answers, keyed by normalized question hash.

    Lives only for the duration of a session — no persistence.
    """

    def __init__(self, max_size: int = 50) -> None:
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._max_size = max_size

    def get(self, question: str) -> Optional[str]:
        """Look up a cached answer by question text."""
        key = question_hash(question)
        if key in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            logger.info(f"Cache hit for: {question[:50]}...")
            return self._cache[key]
        return None

    def put(self, question: str, answer: str) -> None:
        """Store an answer in the cache."""
        key = question_hash(question)
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = answer

        # Evict oldest if over capacity
        while len(self._cache) > self._max_size:
            evicted_key, _ = self._cache.popitem(last=False)
            logger.debug(f"Cache evicted: {evicted_key}")

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)
