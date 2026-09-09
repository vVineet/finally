from __future__ import annotations

from app.db import Position
from app.market import PriceCache
from app.portfolio import build_position_view, compute_total_value


def _position(ticker: str, quantity: float, avg_cost: float) -> Position:
    return Position(
        id="id-1", user_id="default", ticker=ticker, quantity=quantity, avg_cost=avg_cost,
        updated_at="2026-01-01T00:00:00+00:00",
    )


def test_compute_total_value_sums_cash_and_priced_positions():
    cache = PriceCache()
    cache.update("AAPL", 200.0)
    cache.update("MSFT", 400.0)
    positions = [_position("AAPL", 10, 180.0), _position("MSFT", 5, 350.0)]

    total = compute_total_value(1000.0, positions, cache)

    assert total == 1000.0 + 10 * 200.0 + 5 * 400.0


def test_compute_total_value_excludes_tickers_with_no_cached_price():
    cache = PriceCache()
    cache.update("AAPL", 200.0)
    positions = [_position("AAPL", 10, 180.0), _position("ZZZZ", 5, 10.0)]

    total = compute_total_value(1000.0, positions, cache)

    # ZZZZ is excluded entirely, not valued at 0 or avg_cost.
    assert total == 1000.0 + 10 * 200.0


def test_compute_total_value_with_no_positions_is_just_cash():
    cache = PriceCache()
    assert compute_total_value(1234.56, [], cache) == 1234.56


def test_build_position_view_computes_pnl():
    cache = PriceCache()
    cache.update("AAPL", 200.0)
    position = _position("AAPL", 10, 180.0)

    view = build_position_view(position, cache)

    assert view.current_price == 200.0
    assert view.market_value == 2000.0
    assert view.unrealized_pnl == 200.0  # (200-180)*10
    assert view.unrealized_pnl_percent == round(200.0 / 1800.0 * 100, 4)


def test_build_position_view_no_price_returns_nones_not_zero():
    cache = PriceCache()
    position = _position("ZZZZ", 10, 180.0)

    view = build_position_view(position, cache)

    assert view.current_price is None
    assert view.market_value is None
    assert view.unrealized_pnl is None
    assert view.unrealized_pnl_percent is None
    assert view.to_dict()["ticker"] == "ZZZZ"
