"""
Heuristic question pre-filter.

Cheap regex/keyword check to decide whether a transcript fragment
is worth sending to the LLM. This avoids wasting LLM calls on
filler speech like "okay, let's move on."
"""

from __future__ import annotations

import re

# Question-starting patterns (case-insensitive)
QUESTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bwhat\s+is\b",
        r"\bwhat\s+are\b",
        r"\bwhat\s+does\b",
        r"\bwhat\s+do\b",
        r"\bwhat\s+happens\b",
        r"\bwhy\s+",
        r"\bhow\s+",
        r"\bexplain\b",
        r"\bdefine\b",
        r"\bdescribe\b",
        r"\bdifference\s+between\b",
        r"\bcompare\b",
        r"\bcan\s+you\s+explain\b",
        r"\btell\s+me\s+about\b",
        r"\bwrite\s+a\s+(program|function|code|script)\b",
        r"\bimplement\b",
        r"\btime\s+complexity\b",
        r"\bspace\s+complexity\b",
        r"\bwhat\s+is\s+the\s+output\b",
        r"\bgive\s+(an?\s+)?example\b",
        r"\bwhen\s+would\s+you\s+use\b",
        r"\bwhat\s+.*\s+vs\b",
        r"\b\w+\s+vs\.?\s+\w+\b",
    ]
]

# Terminal question mark is a strong signal
QUESTION_MARK = re.compile(r"\?\s*$")

# Minimum word count — very short fragments are usually not questions
MIN_WORDS = 3


def score_question(text: str) -> float:
    """
    Score how likely a transcript fragment is a programming question.

    Returns a float between 0.0 and 1.0.
    Higher = more likely a question worth answering.
    """
    text = text.strip()
    if not text:
        return 0.0

    words = text.split()
    if len(words) < MIN_WORDS:
        return 0.0

    score = 0.0

    # Question mark is a strong signal
    if QUESTION_MARK.search(text):
        score += 0.5

    # Pattern matches
    pattern_matches = sum(1 for p in QUESTION_PATTERNS if p.search(text))
    if pattern_matches > 0:
        score += min(0.5, pattern_matches * 0.2)

    # Longer questions are more likely to be real questions
    if len(words) >= 6:
        score += 0.1

    return min(1.0, score)
