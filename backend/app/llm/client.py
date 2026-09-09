"""Real LiteLLM -> OpenRouter -> Cerebras call (per the `cerebras` skill).

Any failure (network, timeout, malformed provider response, missing
content) is wrapped in `LLMCallError` -- the route handler catches this
and falls back to the apology message (planning/LLM_DESIGN.md §5), never
lets it become a 500.
"""

from __future__ import annotations

from litellm import completion

from .config import EXTRA_BODY, MODEL
from .schema import LLMChatResponse

REQUEST_TIMEOUT_SECONDS = 30


class LLMCallError(Exception):
    """Wraps any failure calling the model (network, timeout, empty
    response, provider error)."""


def call_llm(messages: list[dict]) -> str:
    """Returns the raw JSON string the model produced. Callers pass it to
    `app.llm.parser.parse_llm_response`."""
    try:
        response = completion(
            model=MODEL,
            messages=messages,
            response_format=LLMChatResponse,
            reasoning_effort="low",
            extra_body=EXTRA_BODY,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 - deliberately broad, see module docstring
        raise LLMCallError(f"LLM call failed: {exc}") from exc

    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise LLMCallError("LLM response had no choices/content") from exc

    if not content:
        raise LLMCallError("LLM response content was empty")
    return content
