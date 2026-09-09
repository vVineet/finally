"""build_messages: system+context / history / new-message assembly, and
B10's rule that history is content-only (actions never replayed)."""

from __future__ import annotations

from app.db import ChatMessage
from app.llm.context import PortfolioContext
from app.llm.prompts import SYSTEM_PROMPT, build_messages


def _context() -> PortfolioContext:
    return PortfolioContext(cash_balance=10000.0, total_value=10000.0, positions=[], watchlist=[])


def test_system_prompt_forbids_completion_language():
    lowered = SYSTEM_PROMPT.lower()
    assert "never say" in lowered
    assert "i bought" in lowered or "bought 10 aapl" in lowered  # cited as the forbidden example


def test_build_messages_shape():
    history = [
        ChatMessage(
            id="1", user_id="default", role="user", content="hi", actions=None, created_at="t"
        ),
        ChatMessage(
            id="2",
            user_id="default",
            role="assistant",
            content="hello",
            actions='{"trades_executed": [{"ticker": "AAPL"}]}',
            created_at="t",
        ),
    ]
    messages = build_messages(_context(), history, "buy 10 AAPL")

    assert messages[0]["role"] == "system"
    assert "Cash balance" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "hi"}
    assert messages[2] == {"role": "assistant", "content": "hello"}
    assert messages[-1] == {"role": "user", "content": "buy 10 AAPL"}

    # B10: actions are never replayed into the model's own message list.
    serialized = str(messages)
    assert "trades_executed" not in serialized


def test_build_messages_defaults_unknown_role_to_user():
    history = [
        ChatMessage(id="1", user_id="default", role="system", content="weird", actions=None, created_at="t")
    ]
    messages = build_messages(_context(), history, "hello")
    assert messages[1] == {"role": "user", "content": "weird"}
