"""Prompt construction, the Groq seam, and deterministic response validation.

Phase 7 exports the four pieces the pipeline and the eval harness need:
the versioned system prompt, the structured-output schema, the client, and the
pure validator.
"""

from __future__ import annotations

from .answer import strip_ungrounded_numbers, validate_response
from .groq_client import GenerationError, GroqClient, error_payload, is_error_payload
from .prompts import (
    ANSWER_SCHEMA,
    MAX_SENTENCES,
    SYSTEM_PROMPT_V1,
    allowed_urls,
    build_user_prompt,
    citation_candidates,
)

__all__ = [
    "ANSWER_SCHEMA",
    "GenerationError",
    "GroqClient",
    "MAX_SENTENCES",
    "SYSTEM_PROMPT_V1",
    "allowed_urls",
    "build_user_prompt",
    "citation_candidates",
    "error_payload",
    "is_error_payload",
    "strip_ungrounded_numbers",
    "validate_response",
]
