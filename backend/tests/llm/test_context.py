"""build_portfolio_context / to_prompt_text -- the prompt-facing context
bundle (planning/LLM_DESIGN.md §4). Unlike GET /api/watchlist (C3), this
includes live prices since it's prompt content, never a response body.
"""

from __future__ import annotations

from app.db import add_to_watchlist
from app.llm.context import build_portfolio_context, to_prompt_text
from app.llm.executor import execute_trades
from app.llm.schema import LLMTrade


async def test_empty_portfolio_context(price_cache):
    context = await build_portfolio_context(price_cache)
    assert context.cash_balance == 10000.0
    assert context.total_value == 10000.0
    assert context.positions == []
    # A fresh DB seeds the 10 default watchlist tickers (PLAN §7) -- not
    # empty. The price_cache fixture only seeds AAPL/TSLA, so the rest have
    # no cached price yet.
    assert len(context.watchlist) == 10
    watchlist_prices = {w.ticker: w.current_price for w in context.watchlist}
    assert watchlist_prices["AAPL"] == 200.0
    assert watchlist_prices["TSLA"] == 250.0
    assert watchlist_prices["GOOGL"] is None


async def test_context_includes_positions_and_watchlist_prices(price_cache):
    await execute_trades([LLMTrade(ticker="AAPL", side="buy", quantity=10)], price_cache)
    await add_to_watchlist("TSLA")

    context = await build_portfolio_context(price_cache)
    assert len(context.positions) == 1
    assert context.positions[0].ticker == "AAPL"
    assert context.positions[0].current_price == 200.0

    watchlist_tickers = {w.ticker: w.current_price for w in context.watchlist}
    assert watchlist_tickers["AAPL"] == 200.0
    assert watchlist_tickers["TSLA"] == 250.0


async def test_watchlist_ticker_with_no_cached_price_is_none(price_cache):
    await add_to_watchlist("ZZZZ")
    context = await build_portfolio_context(price_cache)
    watchlist_tickers = {w.ticker: w.current_price for w in context.watchlist}
    assert watchlist_tickers["ZZZZ"] is None


def test_to_prompt_text_renders_without_crashing_when_empty(price_cache):
    from app.llm.context import PortfolioContext

    context = PortfolioContext(cash_balance=10000.0, total_value=10000.0, positions=[], watchlist=[])
    text = to_prompt_text(context)
    assert "Positions: none" in text
    assert "Watchlist: empty" in text
    assert "$10,000.00" in text


def test_to_prompt_text_renders_populated_positions_and_watchlist():
    from app.llm.context import PortfolioContext, WatchlistLine
    from app.portfolio.valuation import PositionView

    context = PortfolioContext(
        cash_balance=8000.0,
        total_value=10120.0,
        positions=[
            PositionView(
                ticker="AAPL",
                quantity=10,
                avg_cost=200.0,
                current_price=212.0,
                market_value=2120.0,
                unrealized_pnl=120.0,
                unrealized_pnl_percent=6.0,
                updated_at="2026-01-01T00:00:00+00:00",
            ),
            PositionView(
                ticker="ZZZZ",
                quantity=3,
                avg_cost=50.0,
                current_price=None,
                market_value=None,
                unrealized_pnl=None,
                unrealized_pnl_percent=None,
                updated_at="2026-01-01T00:00:00+00:00",
            ),
        ],
        watchlist=[
            WatchlistLine(ticker="AAPL", current_price=212.0),
            WatchlistLine(ticker="PYPL", current_price=None),
        ],
    )
    text = to_prompt_text(context)
    assert "AAPL: 10 shares @ avg cost $200.00, current price $212.00" in text
    assert "unrealized P&L $120.00 (+6.00%)" in text
    assert "ZZZZ: 3 shares" in text
    assert "no live price yet" in text
    assert "PYPL: no live price yet" in text
