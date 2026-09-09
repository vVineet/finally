from __future__ import annotations

import json

from app.db import add_chat_message


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


def test_chat_post_is_stubbed_501(client):
    response = client.post("/api/chat", json={"message": "buy 10 AAPL"})
    assert response.status_code == 501
    assert "detail" in response.json()


def test_chat_post_requires_nonempty_message(client):
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422
