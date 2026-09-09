"""GET /api/history/{ticker} (PLAN §13.B13/C4). Exact response contract:
{"ticker": ..., "points": [{"t": "...Z", "price": ...}, ...]}, oldest
first, 200 + empty points for an unknown/never-ticked ticker.
"""

from __future__ import annotations

from datetime import UTC, datetime


def test_unknown_ticker_returns_200_with_empty_points(client):
    response = client.get("/api/history/ZZZZ")
    assert response.status_code == 200
    assert response.json() == {"ticker": "ZZZZ", "points": []}


def test_history_returns_points_oldest_first(client, price_cache):
    price_cache.update("AAPL", 190.0, timestamp=1_700_000_000.0)
    price_cache.update("AAPL", 191.0, timestamp=1_700_000_000.5)
    price_cache.update("AAPL", 192.0, timestamp=1_700_000_001.0)

    response = client.get("/api/history/AAPL")

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "AAPL"
    prices = [p["price"] for p in body["points"]]
    assert prices == [190.0, 191.0, 192.0]  # oldest first


def test_history_timestamp_is_iso_utc_with_z_suffix(client, price_cache):
    price_cache.update("AAPL", 190.0, timestamp=1_700_000_000.5)

    response = client.get("/api/history/AAPL")

    point = response.json()["points"][0]
    assert point["t"].endswith("Z")
    assert "+00:00" not in point["t"]
    # Round-trips to the same instant (allowing for millisecond rounding).
    parsed = datetime.fromisoformat(point["t"].replace("Z", "+00:00"))
    assert parsed.tzinfo == UTC
    expected = datetime.fromtimestamp(1_700_000_000.5, tz=UTC)
    assert abs((parsed - expected).total_seconds()) < 0.001


def test_history_ticker_is_normalized_case_insensitive(client, price_cache):
    price_cache.update("AAPL", 190.0, timestamp=1.0)

    response = client.get("/api/history/aapl")

    assert response.status_code == 200
    assert response.json()["ticker"] == "AAPL"
    assert len(response.json()["points"]) == 1


def test_history_limit_defaults_to_600_and_returns_most_recent(client, price_cache):
    for i in range(650):
        price_cache.update("AAPL", float(i), timestamp=float(i))

    response = client.get("/api/history/AAPL")

    assert response.status_code == 200
    points = response.json()["points"]
    assert len(points) == 600  # HISTORY_MAXLEN, not all 650 ticks
    assert points[0]["price"] == 50.0  # oldest retained after eviction
    assert points[-1]["price"] == 649.0


def test_history_limit_param_truncates_to_most_recent(client, price_cache):
    for i in range(10):
        price_cache.update("AAPL", float(i), timestamp=float(i))

    response = client.get("/api/history/AAPL?limit=3")

    assert response.status_code == 200
    prices = [p["price"] for p in response.json()["points"]]
    assert prices == [7.0, 8.0, 9.0]


def test_history_limit_is_bounded(client):
    response = client.get("/api/history/AAPL?limit=0")
    assert response.status_code == 422
    assert "detail" in response.json()

    response = client.get("/api/history/AAPL?limit=601")
    assert response.status_code == 422
    assert "detail" in response.json()
