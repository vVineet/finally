"""Parse the model's structured JSON output, never raising in a way that
would surface as a 500 (PLAN §13, "graceful degradation").

See planning/LLM_DESIGN.md §6 for the full rationale and the list of
adversarial inputs this is tested against (tests/llm/test_parser.py).
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from .schema import LLMChatResponse

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


class LLMParseError(Exception):
    """Raised only when nothing usable -- not even a `message` string --
    could be recovered from the model's output. Callers always catch this
    and substitute a generic fallback reply; it must never propagate to a
    route handler as an unhandled exception."""


def _strip_code_fence(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = _FENCE_RE.sub("", stripped).strip()
    return stripped


def parse_llm_response(raw: str) -> LLMChatResponse:
    """Strict parse first; on any failure, salvage just `message` if the
    payload is at least a JSON object with a usable string `message`,
    dropping any malformed trades/watchlist_changes rather than acting on
    a partially-invalid shape. Raises `LLMParseError` only when even that
    salvage fails.
    """
    cleaned = _strip_code_fence(raw)

    try:
        parsed = LLMChatResponse.model_validate_json(cleaned)
        if parsed.message.strip():
            return parsed
        # A blank/whitespace-only message is treated as unusable, same as
        # the lenient path below -- fall through rather than returning it.
    except (ValidationError, ValueError):
        pass

    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        raise LLMParseError("LLM response was not valid JSON") from None

    message = data.get("message") if isinstance(data, dict) else None
    if isinstance(message, str) and message.strip():
        return LLMChatResponse(message=message, trades=[], watchlist_changes=[])

    raise LLMParseError("LLM response had no usable `message` field")
