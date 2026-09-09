"""Trade/watchlist execution reuses the real validated paths (app.db,
app.api.errors.normalize_ticker) -- these tests exercise real DB writes
against an isolated SQLite file per test, per planning/LLM_DESIGN.md §3.
"""

from __future__ import annotations

from app.db import get_cash_balance, get_position, get_watchlist
from app.llm.executor import execute_trades, execute_watchlist_changes
from app.llm.schema import LLMTrade, LLMWatchlistChange


async def test_successful_buy_executes_and_auto_adds_to_watchlist(price_cache):
    executed, failed = await execute_trades(
        [LLMTrade(ticker="AAPL", side="buy", quantity=5)], price_cache
    )
    assert failed == []
    assert len(executed) == 1
    assert executed[0]["status"] == "success"
    assert executed[0]["ticker"] == "AAPL"
    assert executed[0]["price"] == 200.0

    position = await get_position("AAPL")
    assert position is not None
    assert position.quantity == 5

    watchlist = await get_watchlist()
    assert any(w.ticker == "AAPL" for w in watchlist)


async def test_successful_sell_reduces_position(price_cache):
    await execute_trades([LLMTrade(ticker="AAPL", side="buy", quantity=10)], price_cache)
    executed, failed = await execute_trades(
        [LLMTrade(ticker="AAPL", side="sell", quantity=4)], price_cache
    )
    assert failed == []
    assert executed[0]["side"] == "sell"
    position = await get_position("AAPL")
    assert position.quantity == 6


async def test_insufficient_cash_reported_as_failed_not_raised(price_cache):
    executed, failed = await execute_trades(
        [LLMTrade(ticker="AAPL", side="buy", quantity=1_000_000)], price_cache
    )
    assert executed == []
    assert len(failed) == 1
    assert failed[0]["status"] == "failed"
    assert "Insufficient cash" in failed[0]["error"]
    # Cash balance untouched.
    assert await get_cash_balance() == 10000.0


async def test_insufficient_shares_reported_as_failed(price_cache):
    executed, failed = await execute_trades(
        [LLMTrade(ticker="AAPL", side="sell", quantity=5)], price_cache
    )
    assert executed == []
    assert "Insufficient shares" in failed[0]["error"]


async def test_no_cached_price_reported_as_failed(price_cache):
    executed, failed = await execute_trades(
        [LLMTrade(ticker="ZZZZ", side="buy", quantity=1)], price_cache
    )
    assert executed == []
    assert "No live price available for ZZZZ" in failed[0]["error"]


async def test_bad_ticker_format_reported_as_failed_not_raised(price_cache):
    executed, failed = await execute_trades(
        [LLMTrade(ticker="1BADTICKER!!", side="buy", quantity=1)], price_cache
    )
    assert executed == []
    assert failed[0]["status"] == "failed"
    assert "Invalid ticker format" in failed[0]["error"]


async def test_zero_and_negative_quantity_reported_as_failed(price_cache):
    executed, failed = await execute_trades(
        [
            LLMTrade(ticker="AAPL", side="buy", quantity=0),
            LLMTrade(ticker="AAPL", side="buy", quantity=-5),
        ],
        price_cache,
    )
    assert executed == []
    assert len(failed) == 2
    assert all("positive, finite" in f["error"] for f in failed)


async def test_mixed_batch_partitions_into_executed_and_failed(price_cache):
    executed, failed = await execute_trades(
        [
            LLMTrade(ticker="AAPL", side="buy", quantity=5),
            LLMTrade(ticker="AAPL", side="buy", quantity=1_000_000),
        ],
        price_cache,
    )
    assert len(executed) == 1
    assert len(failed) == 1


async def test_watchlist_add(price_cache):
    results = await execute_watchlist_changes([LLMWatchlistChange(ticker="PYPL", action="add")])
    assert results == [{"ticker": "PYPL", "action": "add", "status": "success"}]
    watchlist = await get_watchlist()
    assert any(w.ticker == "PYPL" for w in watchlist)


async def test_watchlist_add_is_idempotent(price_cache):
    await execute_watchlist_changes([LLMWatchlistChange(ticker="PYPL", action="add")])
    results = await execute_watchlist_changes([LLMWatchlistChange(ticker="PYPL", action="add")])
    assert results[0]["status"] == "success"


async def test_watchlist_remove_success(price_cache):
    await execute_watchlist_changes([LLMWatchlistChange(ticker="PYPL", action="add")])
    results = await execute_watchlist_changes([LLMWatchlistChange(ticker="PYPL", action="remove")])
    assert results == [{"ticker": "PYPL", "action": "remove", "status": "success"}]


async def test_watchlist_remove_not_present_reported_as_failed(price_cache):
    results = await execute_watchlist_changes([LLMWatchlistChange(ticker="ZZZZ", action="remove")])
    assert results[0]["status"] == "failed"
    assert "ZZZZ is not on the watchlist" in results[0]["error"]


async def test_watchlist_bad_ticker_format_reported_as_failed(price_cache):
    results = await execute_watchlist_changes(
        [LLMWatchlistChange(ticker="!!!", action="add")]
    )
    assert results[0]["status"] == "failed"
    assert "Invalid ticker format" in results[0]["error"]


async def test_empty_lists_are_no_ops(price_cache):
    executed, failed = await execute_trades([], price_cache)
    assert executed == [] and failed == []
    results = await execute_watchlist_changes([])
    assert results == []
