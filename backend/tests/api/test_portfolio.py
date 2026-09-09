from __future__ import annotations


def test_get_portfolio_initial_state(client):
    response = client.get("/api/portfolio")
    assert response.status_code == 200
    body = response.json()
    assert body["cash_balance"] == 10000.0
    assert body["total_value"] == 10000.0
    assert body["positions"] == []
    assert "updated_at" in body


def test_trade_buy_requires_a_cached_price(client):
    # No price seeded for AAPL in this test's PriceCache.
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1}
    )
    assert response.status_code == 400
    assert "No live price" in response.json()["detail"]


def test_trade_buy_executes_and_returns_updated_portfolio(client, price_cache, market_source):
    price_cache.update("AAPL", 200.0)

    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trade"]["ticker"] == "AAPL"
    assert body["trade"]["side"] == "buy"
    assert body["trade"]["quantity"] == 10
    assert body["trade"]["price"] == 200.0

    portfolio = body["portfolio"]
    assert portfolio["cash_balance"] == 10000.0 - 2000.0
    assert portfolio["total_value"] == 10000.0
    assert len(portfolio["positions"]) == 1
    position = portfolio["positions"][0]
    assert position["ticker"] == "AAPL"
    assert position["quantity"] == 10
    assert position["current_price"] == 200.0
    assert position["unrealized_pnl"] == 0.0

    # Snapshot recorded immediately after the trade.
    history = client.get("/api/portfolio/history").json()
    assert len(history["snapshots"]) == 1
    assert history["snapshots"][0]["total_value"] == 10000.0


def test_trade_auto_adds_ticker_not_on_watchlist(client, price_cache, market_source):
    price_cache.update("PYPL", 50.0)
    client.delete("/api/watchlist/AAPL")  # unrelated, just confirm PYPL isn't already there

    response = client.post(
        "/api/portfolio/trade", json={"ticker": "PYPL", "side": "buy", "quantity": 1}
    )
    assert response.status_code == 200

    watchlist = client.get("/api/watchlist").json()["watchlist"]
    tickers = {item["ticker"] for item in watchlist}
    assert "PYPL" in tickers
    assert "PYPL" in market_source.get_tickers()


def test_trade_rejects_non_positive_quantity(client, price_cache):
    price_cache.update("AAPL", 200.0)
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 0}
    )
    assert response.status_code == 400

    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": -5}
    )
    assert response.status_code == 400


def test_trade_rejects_non_finite_quantity(client, price_cache):
    price_cache.update("AAPL", 200.0)
    # httpx's `json=` param refuses to encode inf/nan (strict JSON), so send
    # the raw body ourselves -- Python's json.loads (used by Starlette) does
    # accept the "Infinity" literal.
    response = client.post(
        "/api/portfolio/trade",
        content='{"ticker": "AAPL", "side": "buy", "quantity": Infinity}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code in (400, 422)


def test_trade_rejects_bad_side(client, price_cache):
    price_cache.update("AAPL", 200.0)
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "hold", "quantity": 1}
    )
    assert response.status_code == 422  # pydantic Literal validation


def test_trade_insufficient_cash(client, price_cache):
    price_cache.update("AAPL", 200.0)
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1000}
    )
    assert response.status_code == 400
    assert "detail" in response.json()


def test_trade_insufficient_shares(client, price_cache):
    price_cache.update("AAPL", 200.0)
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1})
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 5}
    )
    assert response.status_code == 400
    assert "detail" in response.json()


def test_trade_selling_everything_closes_the_position(client, price_cache):
    price_cache.update("AAPL", 200.0)
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 10}
    )
    assert response.status_code == 200
    assert response.json()["portfolio"]["positions"] == []


def test_portfolio_history_bounds_limit(client, price_cache):
    response = client.get("/api/portfolio/history?limit=0")
    assert response.status_code == 422  # ge=1 violated

    response = client.get("/api/portfolio/history?limit=999999")
    assert response.status_code == 422  # le=2000 violated


def test_portfolio_history_rejects_bad_since(client):
    response = client.get("/api/portfolio/history?since=not-a-date")
    assert response.status_code == 400


def test_portfolio_history_filters_by_since(client, price_cache):
    price_cache.update("AAPL", 200.0)
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1})
    first = client.get("/api/portfolio/history").json()["snapshots"]
    assert len(first) == 1
    cutoff = first[0]["recorded_at"]

    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 1})

    since_response = client.get("/api/portfolio/history", params={"since": cutoff}).json()
    assert len(since_response["snapshots"]) >= 1


def test_portfolio_reset_restores_defaults(client, price_cache, market_source):
    price_cache.update("AAPL", 200.0)
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})

    response = client.post("/api/portfolio/reset")
    assert response.status_code == 200
    body = response.json()
    assert body["portfolio"]["cash_balance"] == 10000.0
    assert body["portfolio"]["positions"] == []
    tickers = {item["ticker"] for item in body["watchlist"]}
    assert tickers == {
        "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX",
    }
