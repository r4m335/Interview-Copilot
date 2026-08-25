"""
Streaming answer generator.

Takes a question, checks cache, streams answer deltas to the session's
viewers via WebSocket.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from app.llm.client import llm_client
from app.llm.prompts import SYSTEM_PROMPT, format_question_prompt

logger = logging.getLogger(__name__)

# Sentinel that the LLM returns for non-questions
IGNORE_SENTINEL = "IGNORE"


async def generate_answer_stream(question: str) -> AsyncIterator[str]:
    """
    Stream answer tokens for a detected question.

    Yields individual tokens/chunks from the LLM.
    If the LLM returns IGNORE, yields nothing (empty iterator).
    """
    prompt = format_question_prompt(question)

    accumulated = ""
    is_ignore = False

    async for token in llm_client.stream(prompt, SYSTEM_PROMPT):
        accumulated += token

        # Check for IGNORE early (within first few tokens)
        if len(accumulated) <= 10:
            if accumulated.strip().upper().startswith(IGNORE_SENTINEL):
                is_ignore = True
                logger.info(f"LLM returned IGNORE for: {question[:50]}...")
                return

        if not is_ignore:
            yield token

    # Final check — if the entire response is just IGNORE
    if accumulated.strip().upper() == IGNORE_SENTINEL:
        logger.info(f"LLM returned IGNORE for: {question[:50]}...")


async def generate_answer_complete(question: str) -> str | None:
    """
    Generate a complete answer (non-streaming).

    Returns None if the LLM returns IGNORE.
    """
    prompt = format_question_prompt(question)
    response = await llm_client.generate(prompt, SYSTEM_PROMPT)

    if response.strip().upper() == IGNORE_SENTINEL:
        logger.info(f"LLM returned IGNORE for: {question[:50]}...")
        return None

    return response
