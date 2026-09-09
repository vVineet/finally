"""Mock-mode keyword extraction (planning/LLM_DESIGN.md §7). Covers the
trade path, the watchlist path, and plain chat -- the three the
Integration Tester depends on for E2E coverage per PLAN §13.
"""

from __future__ import annotations

from app.llm.context import PortfolioContext
from app.llm.mock import build_mock_raw_response, build_mock_response
from app.llm.parser import parse_llm_response
from app.portfolio.valuation import PositionView


def _empty_context(cash: float = 10_000.0) -> PortfolioContext:
    return PortfolioContext(cash_balance=cash, total_value=cash, positions=[], watchlist=[])


def test_buy_with_explicit_quantity_and_shares_of_phrasing():
    result = build_mock_response("Buy 10 shares of AAPL", _empty_context())
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.ticker == "AAPL"
    assert trade.side == "buy"
    assert trade.quantity == 10
    assert "I'll" in result.message
    assert "bought" not in result.message.lower()


def test_sell_with_bare_ticker():
    result = build_mock_response("Sell 5 TSLA", _empty_context())
    assert result.trades[0] == build_mock_response("Sell 5 TSLA", _empty_context()).trades[0]
    trade = result.trades[0]
    assert trade.ticker == "TSLA"
    assert trade.side == "sell"
    assert trade.quantity == 5


def test_buy_without_quantity_defaults_to_one():
    result = build_mock_response("buy AAPL please", _empty_context())
    assert result.trades[0].quantity == 1.0


def test_watchlist_add():
    result = build_mock_response("Add PYPL to my watchlist", _empty_context())
    assert result.trades == []
    assert len(result.watchlist_changes) == 1
    change = result.watchlist_changes[0]
    assert change.ticker == "PYPL"
    assert change.action == "add"
    assert "added" not in result.message.lower()


def test_watchlist_remove():
    result = build_mock_response("Remove NFLX from the watchlist", _empty_context())
    change = result.watchlist_changes[0]
    assert change.ticker == "NFLX"
    assert change.action == "remove"


def test_watchlist_delete_synonym():
    result = build_mock_response("please delete GOOGL from my watchlist", _empty_context())
    assert result.watchlist_changes[0].action == "remove"
    assert result.watchlist_changes[0].ticker == "GOOGL"


def test_plain_chat_falls_back_to_context_derived_reply():
    context = PortfolioContext(
        cash_balance=5000.0,
        total_value=7500.0,
        positions=[
            PositionView(
                ticker="AAPL",
                quantity=10,
                avg_cost=200.0,
                current_price=250.0,
                market_value=2500.0,
                unrealized_pnl=500.0,
                unrealized_pnl_percent=25.0,
                updated_at="2026-01-01T00:00:00+00:00",
            )
        ],
        watchlist=[],
    )
    result = build_mock_response("What does my portfolio look like?", context)
    assert result.trades == []
    assert result.watchlist_changes == []
    assert "5,000.00" in result.message
    assert "7,500.00" in result.message
    assert "1 open position" in result.message


def test_plain_chat_is_deterministic_for_same_context():
    context = _empty_context()
    first = build_mock_response("hello there", context)
    second = build_mock_response("hello there", context)
    assert first.message == second.message


def test_watchlist_keyword_without_add_or_remove_verb_falls_back_to_chat():
    result = build_mock_response("What's on my watchlist?", _empty_context())
    assert result.watchlist_changes == []
    assert result.trades == []


def test_watchlist_add_without_a_recognizable_ticker_falls_back_to_chat():
    result = build_mock_response("please add it to the watchlist", _empty_context())
    assert result.watchlist_changes == []


def test_sell_all_phrasing_is_a_documented_limitation_falls_back_to_chat():
    # "all" isn't a ticker; the mock doesn't guess, and doesn't crash.
    result = build_mock_response("sell all my TSLA", _empty_context())
    assert result.trades == []


def test_build_mock_raw_response_round_trips_through_the_real_parser():
    context = _empty_context()
    raw = build_mock_raw_response("Buy 10 AAPL", context)
    parsed = parse_llm_response(raw)
    assert parsed.trades[0].ticker == "AAPL"
