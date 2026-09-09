from __future__ import annotations


def test_list_trades_empty_initially(client):
    response = client.get("/api/trades")
    assert response.status_code == 200
    assert response.json() == {"trades": []}


def test_list_trades_after_a_trade(client, price_cache):
    price_cache.update("AAPL", 150.0)
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 3})

    response = client.get("/api/trades")
    assert response.status_code == 200
    trades = response.json()["trades"]
    assert len(trades) == 1
    assert trades[0]["ticker"] == "AAPL"
    assert trades[0]["side"] == "buy"
    assert trades[0]["quantity"] == 3
    assert trades[0]["price"] == 150.0
    assert "executed_at" in trades[0]


def test_list_trades_limit_is_bounded(client):
    response = client.get("/api/trades?limit=0")
    assert response.status_code == 422

    response = client.get("/api/trades?limit=1000000")
    assert response.status_code == 422
