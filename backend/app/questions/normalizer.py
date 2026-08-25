"""
Question normalizer — strips filler, lowercases, hashes for cache keys.
"""

from __future__ import annotations

import hashlib
import re

# Filler words to remove before hashing
FILLER_WORDS = {
    "um", "uh", "like", "you know", "so", "okay", "ok",
    "well", "actually", "basically", "right", "i mean",
    "let me think", "hmm", "ah",
}

# Multiple spaces / punctuation
_MULTI_SPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^\w\s]")


def normalize_question(text: str) -> str:
    """
    Normalize a question for comparison / caching.

    Steps:
      1. Lowercase
      2. Remove punctuation
      3. Remove filler words
      4. Collapse whitespace
      5. Strip
    """
    text = text.lower()
    text = _PUNCTUATION.sub("", text)

    for filler in FILLER_WORDS:
        text = text.replace(filler, " ")

    text = _MULTI_SPACE.sub(" ", text).strip()
    return text


def question_hash(text: str) -> str:
    """
    Generate a short hash of a normalized question for cache lookup.
    """
    normalized = normalize_question(text)
    return hashlib.md5(normalized.encode()).hexdigest()[:12]
