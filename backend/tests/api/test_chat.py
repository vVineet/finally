from __future__ import annotations

import json

import app.api.chat as chat_module
from app.db import add_chat_message, add_to_watchlist
from app.llm import LLMCallError


def test_chat_history_empty_initially(client):
    response = client.get("/api/chat/history")
    assert response.status_code == 200
    assert response.json() == {"messages": []}


async def test_chat_history_returns_persisted_messages(client):
    await add_chat_message(role="user", content="hi")
    await add_chat_message(
        role="assistant", content="hello", actions=json.dumps({"trades": []})
    )

    response = client.get("/api/chat/history")
    assert response.status_code == 200
    messages = response.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["actions"] is None
    assert messages[1]["role"] == "assistant"
    assert messages[1]["actions"] == {"trades": []}


def test_chat_post_requires_nonempty_message(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422


def test_chat_returns_503_when_unconfigured(client, monkeypatch):
    monkeypatch.delenv("LLM_MOCK", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 503
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_chat_plain_message_mock_mode(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    response = client.post("/api/chat", json={"message": "How is my portfolio doing?"})
    assert response.status_code == 200
    body = response.json()
    assert "cash" in body["message"].lower()
    assert body["trades_executed"] == []
    assert body["trades_failed"] == []
    assert body["watchlist_changes"] == []
    assert body["portfolio"]["cash_balance"] == 10000.0
    assert isinstance(body["watchlist"], list)


def test_chat_successful_trade_mock_mode(client, monkeypatch, price_cache):
    monkeypatch.setenv("LLM_MOCK", "true")
    price_cache.update("AAPL", 200.0)

    response = client.post("/api/chat", json={"message": "Buy 10 shares of AAPL"})
    assert response.status_code == 200
    body = response.json()
    assert "I'll" in body["message"]
    assert "bought" not in body["message"].lower()
    assert len(body["trades_executed"]) == 1
    assert body["trades_executed"][0] == {
        "ticker": "AAPL",
        "side": "buy",
        "quantity": 10.0,
        "price": 200.0,
        "status": "success",
    }
    assert body["trades_failed"] == []
    assert body["portfolio"]["cash_balance"] == 8000.0
    assert any(p["ticker"] == "AAPL" for p in body["portfolio"]["positions"])
    assert any(w["ticker"] == "AAPL" for w in body["watchlist"])

    # Persisted with actions.
    history = client.get("/api/chat/history").json()["messages"]
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Buy 10 shares of AAPL"
    assert history[1]["role"] == "assistant"
    assert history[1]["actions"]["trades_executed"][0]["ticker"] == "AAPL"


def test_chat_failed_trade_mock_mode(client, monkeypatch, price_cache):
    monkeypatch.setenv("LLM_MOCK", "true")
    price_cache.update("AAPL", 200.0)

    response = client.post("/api/chat", json={"message": "Buy 1000000 AAPL"})
    assert response.status_code == 200
    body = response.json()
    assert body["trades_executed"] == []
    assert len(body["trades_failed"]) == 1
    assert body["trades_failed"][0]["status"] == "failed"
    assert "Insufficient cash" in body["trades_failed"][0]["error"]
    # Cash untouched by the failed trade.
    assert body["portfolio"]["cash_balance"] == 10000.0


def test_chat_trade_with_no_cached_price_fails_cleanly(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    response = client.post("/api/chat", json={"message": "Buy 10 ZZZZ"})
    assert response.status_code == 200
    body = response.json()
    assert body["trades_executed"] == []
    assert "No live price available for ZZZZ" in body["trades_failed"][0]["error"]


async def test_chat_watchlist_add_mock_mode(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    response = client.post("/api/chat", json={"message": "Add PYPL to my watchlist"})
    assert response.status_code == 200
    body = response.json()
    assert body["watchlist_changes"] == [{"ticker": "PYPL", "action": "add", "status": "success"}]
    assert any(w["ticker"] == "PYPL" for w in body["watchlist"])


async def test_chat_watchlist_remove_not_present_mock_mode(client, monkeypatch):
    # ZZZZ (not one of the 10 seeded defaults) genuinely isn't on the watchlist.
    monkeypatch.setenv("LLM_MOCK", "true")
    response = client.post("/api/chat", json={"message": "Remove ZZZZ from the watchlist"})
    assert response.status_code == 200
    body = response.json()
    assert body["watchlist_changes"] == [
        {
            "ticker": "ZZZZ",
            "action": "remove",
            "status": "failed",
            "error": "ZZZZ is not on the watchlist",
        }
    ]


async def test_chat_watchlist_remove_present_mock_mode(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    await add_to_watchlist("PYPL")
    response = client.post("/api/chat", json={"message": "Remove PYPL from the watchlist"})
    body = response.json()
    assert body["watchlist_changes"] == [{"ticker": "PYPL", "action": "remove", "status": "success"}]
    assert not any(w["ticker"] == "PYPL" for w in body["watchlist"])


def test_chat_response_watchlist_field_is_a_bare_array_not_wrapped(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    response = client.post("/api/chat", json={"message": "hello"})
    body = response.json()
    assert isinstance(body["watchlist"], list)
    for item in body["watchlist"]:
        assert set(item.keys()) == {"ticker", "added_at"}


def test_chat_real_call_path_success(client, monkeypatch):
    """Not mock mode: exercises build_messages + call_llm + parse_llm_response
    end to end, with call_llm monkeypatched so no network call happens."""
    monkeypatch.delenv("LLM_MOCK", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.setattr(
        chat_module,
        "call_llm",
        lambda messages: json.dumps({"message": "Real call worked.", "trades": [], "watchlist_changes": []}),
    )

    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 200
    assert response.json()["message"] == "Real call worked."


def test_chat_llm_call_error_returns_502_not_a_fake_reply(client, monkeypatch):
    """An upstream/provider failure (network, timeout, 5xx, insufficient
    credits, etc.) must surface as a real error (C5's uniform {"detail":
    ...} shape), never a 200 carrying synthetic assistant prose -- that
    would be indistinguishable from a genuine reply to the frontend/user,
    and would pollute chat history with a message the model never wrote.
    """
    monkeypatch.delenv("LLM_MOCK", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")

    def _raise(messages):
        raise LLMCallError("network exploded")

    monkeypatch.setattr(chat_module, "call_llm", _raise)

    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 502
    assert "detail" in response.json()

    # The user's message is persisted; no synthetic assistant turn is.
    history = client.get("/api/chat/history").json()["messages"]
    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "hello"


def test_chat_parse_failure_returns_502_not_a_fake_reply(client, monkeypatch):
    monkeypatch.delenv("LLM_MOCK", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.setattr(chat_module, "call_llm", lambda messages: "not valid json at all")

    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 502
    assert "detail" in response.json()

    history = client.get("/api/chat/history").json()["messages"]
    assert len(history) == 1
    assert history[0]["role"] == "user"
