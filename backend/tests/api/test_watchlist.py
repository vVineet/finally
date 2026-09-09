from __future__ import annotations

DEFAULT_WATCHLIST = {"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"}


def test_get_watchlist_returns_tickers_without_prices(client):
    response = client.get("/api/watchlist")
    assert response.status_code == 200
    body = response.json()
    tickers = {item["ticker"] for item in body["watchlist"]}
    assert tickers == DEFAULT_WATCHLIST
    for item in body["watchlist"]:
        assert set(item.keys()) == {"ticker", "added_at"}  # no price fields (C3)


def test_add_ticker_returns_updated_watchlist(client, market_source):
    response = client.post("/api/watchlist", json={"ticker": "pypl"})
    assert response.status_code == 200
    tickers = {item["ticker"] for item in response.json()["watchlist"]}
    assert "PYPL" in tickers  # normalized to uppercase
    assert "PYPL" in market_source.get_tickers()  # A4: synced to market source


def test_add_ticker_is_idempotent(client):
    client.post("/api/watchlist", json={"ticker": "PYPL"})
    response = client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert response.status_code == 200
    tickers = [item["ticker"] for item in response.json()["watchlist"]]
    assert tickers.count("PYPL") == 1


def test_add_ticker_rejects_bad_format(client):
    # Short enough to pass pydantic's max_length, but not a valid ticker
    # shape (normalize_ticker's regex gate, tested independently of length).
    response = client.post("/api/watchlist", json={"ticker": "@@@"})
    assert response.status_code == 400
    assert "detail" in response.json()


def test_remove_ticker_returns_updated_watchlist(client, market_source):
    response = client.delete("/api/watchlist/AAPL")
    assert response.status_code == 200
    tickers = {item["ticker"] for item in response.json()["watchlist"]}
    assert "AAPL" not in tickers
    assert "AAPL" not in market_source.get_tickers()


def test_remove_unknown_ticker_is_404(client):
    response = client.delete("/api/watchlist/ZZZZ")
    assert response.status_code == 404
    assert response.json() == {"detail": "ZZZZ is not on the watchlist"}


def test_remove_ticker_still_held_keeps_pricing_it(client, market_source, price_cache):
    price_cache.update("AAPL", 190.0)
    trade_response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1}
    )
    assert trade_response.status_code == 200

    response = client.delete("/api/watchlist/AAPL")
    assert response.status_code == 200
    tickers = {item["ticker"] for item in response.json()["watchlist"]}
    assert "AAPL" not in tickers  # removed from the watchlist itself

    # A4: still held, so the market source must still be pricing it.
    assert "AAPL" in market_source.get_tickers()
