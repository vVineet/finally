"""Env-driven configuration for the LLM component (PLAN §5, §13.B11).

Both `is_mock_mode()` and `has_api_key()` re-read the environment on every
call rather than caching at import time, so a request always sees the
current configuration (matters for tests that monkeypatch env vars, and
for an operator fixing `.env` and restarting the process).

The one thing evaluated at *import* time is the startup warning below --
`app/api/chat.py` imports this module, which is imported by `app.main` at
process start, so this doubles as the "startup warning" §13.B11 asks for
without needing to touch `app/main.py` (owned by the Backend API
Engineer).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
# Pin Cerebras as the inference provider, per the cerebras skill.
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}


def is_mock_mode() -> bool:
    return os.environ.get("LLM_MOCK", "").strip().lower() == "true"


def has_api_key() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())


def _warn_if_unconfigured() -> None:
    if not is_mock_mode() and not has_api_key():
        logger.warning(
            "OPENROUTER_API_KEY is not set; POST /api/chat will return a 503 "
            "until it is configured (or set LLM_MOCK=true for testing). "
            "The rest of the app (prices, portfolio, watchlist) is unaffected."
        )


_warn_if_unconfigured()
