"""Tests for the async repository API in app.db.repository."""

from __future__ import annotations

import math

import pytest

from app.db import (
    DEFAULT_USER_ID,
    InsufficientCashError,
    InsufficientSharesError,
    InvalidTradeError,
    add_chat_message,
    add_to_watchlist,
    execute_trade,
    get_cash_balance,
    get_chat_history,
    get_db_path,
    get_position,
    get_positions,
    get_snapshots,
    get_trades,
    get_user_profile,
    get_watchlist,
    init_db,
    record_snapshot,
    remove_from_watchlist,
    reset_portfolio,
)


class TestInitDbAndPath:
    async def test_init_db_is_callable_and_idempotent(self, db_path):
        await init_db()
        await init_db()
        assert await get_cash_balance() == 10000.0

    def test_get_db_path_defaults_to_repo_root_db_dir(self, monkeypatch):
        monkeypatch.delenv("DATABASE_PATH", raising=False)
        path = get_db_path()
        assert path.name == "finally.db"
        assert path.parent.name == "db"


class TestUserProfile:
    async def test_get_user_profile_returns_seeded_default(self, db_path):
        profile = await get_user_profile()
        assert profile.id == DEFAULT_USER_ID
        assert profile.cash_balance == 10000.0
        assert profile.created_at

    async def test_get_cash_balance(self, db_path):
        assert await get_cash_balance() == 10000.0


class TestWatchlist:
    async def test_get_watchlist_returns_ten_defaults(self, db_path):
        items = await get_watchlist()
        assert len(items) == 10
        assert {i.ticker for i in items} == {
            "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX",
        }

    async def test_add_to_watchlist_normalizes_ticker(self, db_path):
        item = await add_to_watchlist("  pypl ")
        assert item.ticker == "PYPL"

    async def test_add_to_watchlist_is_idempotent(self, db_path):
        first = await add_to_watchlist("PYPL")
        second = await add_to_watchlist("pypl")
        assert first.id == second.id
        items = await get_watchlist()
        assert sum(1 for i in items if i.ticker == "PYPL") == 1

    async def test_remove_from_watchlist_returns_true_when_present(self, db_path):
        removed = await remove_from_watchlist("AAPL")
        assert removed is True
        tickers = {i.ticker for i in await get_watchlist()}
        assert "AAPL" not in tickers

    async def test_remove_from_watchlist_returns_false_when_absent(self, db_path):
        removed = await remove_from_watchlist("NOPE")
        assert removed is False


class TestPositionsEmpty:
    async def test_no_positions_initially(self, db_path):
        assert await get_positions() == []

    async def test_get_position_none_when_not_held(self, db_path):
        assert await get_position("AAPL") is None


class TestExecuteTradeValidation:
    async def test_rejects_bad_side(self, db_path):
        with pytest.raises(InvalidTradeError):
            await execute_trade("AAPL", "hold", 1, 100.0)

    @pytest.mark.parametrize("quantity", [0, -5, math.nan, math.inf])
    async def test_rejects_bad_quantity(self, db_path, quantity):
        with pytest.raises(InvalidTradeError):
            await execute_trade("AAPL", "buy", quantity, 100.0)

    @pytest.mark.parametrize("price", [0, -1.0, math.nan, math.inf])
    async def test_rejects_bad_price(self, db_path, price):
        """A caller must never be able to pass a nonsensical stand-in price
        (e.g. 0 for 'no price available') and have it silently accepted."""
        with pytest.raises(InvalidTradeError):
            await execute_trade("AAPL", "buy", 1, price)

    async def test_bad_trade_writes_nothing(self, db_path):
        with pytest.raises(InvalidTradeError):
            await execute_trade("AAPL", "buy", -1, 100.0)
        assert await get_positions() == []
        assert await get_trades() == []
        assert await get_cash_balance() == 10000.0


class TestExecuteTradeBuy:
    async def test_buy_creates_position_and_debits_cash(self, db_path):
        result = await execute_trade("AAPL", "buy", 10, 100.0)
        assert result.position is not None
        assert result.position.ticker == "AAPL"
        assert result.position.quantity == 10
        assert result.position.avg_cost == 100.0
        assert result.cash_balance == 9000.0
        assert await get_cash_balance() == 9000.0

    async def test_buy_rejects_insufficient_cash(self, db_path):
        with pytest.raises(InsufficientCashError) as exc_info:
            await execute_trade("AAPL", "buy", 1000, 100.0)  # notional 100,000 > 10,000
        assert exc_info.value.required == 100000.0
        assert exc_info.value.available == 10000.0
        # Nothing written on rejection.
        assert await get_positions() == []
        assert await get_cash_balance() == 10000.0

    async def test_second_buy_updates_weighted_avg_cost(self, db_path):
        await execute_trade("AAPL", "buy", 10, 100.0)  # 10 @ 100
        result = await execute_trade("AAPL", "buy", 10, 200.0)  # 10 @ 200
        # weighted avg = (10*100 + 10*200) / 20 = 150
        assert result.position.quantity == 20
        assert result.position.avg_cost == 150.0

    async def test_buy_records_trade_row(self, db_path):
        await execute_trade("AAPL", "buy", 10, 100.0)
        trades = await get_trades()
        assert len(trades) == 1
        assert trades[0].side == "buy"
        assert trades[0].ticker == "AAPL"
        assert trades[0].quantity == 10
        assert trades[0].price == 100.0

    async def test_buy_cash_rounded_to_cents(self, db_path):
        result = await execute_trade("AAPL", "buy", 3, 33.333)
        # notional = 3 * 33.333 = 99.999 -> rounds to 100.00
        assert result.cash_balance == 9900.0


class TestExecuteTradeSell:
    async def test_sell_partial_updates_position_not_avg_cost(self, db_path):
        await execute_trade("AAPL", "buy", 10, 100.0)
        result = await execute_trade("AAPL", "sell", 4, 150.0)
        assert result.position is not None
        assert result.position.quantity == 6
        assert result.position.avg_cost == 100.0  # unchanged by sell
        assert result.cash_balance == 9000.0 + 4 * 150.0

    async def test_sell_all_deletes_position(self, db_path):
        await execute_trade("AAPL", "buy", 10, 100.0)
        result = await execute_trade("AAPL", "sell", 10, 120.0)
        assert result.position is None
        assert await get_position("AAPL") is None
        assert await get_positions() == []

    async def test_sell_more_than_held_rejected(self, db_path):
        await execute_trade("AAPL", "buy", 10, 100.0)
        with pytest.raises(InsufficientSharesError) as exc_info:
            await execute_trade("AAPL", "sell", 11, 100.0)
        assert exc_info.value.requested == 11
        assert exc_info.value.held == 10
        # Position untouched by the rejected sell.
        position = await get_position("AAPL")
        assert position.quantity == 10

    async def test_sell_without_any_position_rejected(self, db_path):
        with pytest.raises(InsufficientSharesError):
            await execute_trade("AAPL", "sell", 1, 100.0)

    async def test_sell_exact_holding_with_float_noise_succeeds(self, db_path):
        """Selling a quantity that float math would normally leave as a tiny
        residual must still fully close the position (epsilon tolerance)."""
        await execute_trade("AAPL", "buy", 0.1, 100.0)
        await execute_trade("AAPL", "buy", 0.2, 100.0)
        position = await get_position("AAPL")
        # 0.1 + 0.2 != 0.3 exactly in binary float
        result = await execute_trade("AAPL", "sell", position.quantity, 100.0)
        assert result.position is None


class TestFloatResidualRule:
    """Direct test of the < 1e-9 deletion rule (B5) using the sync core, to
    pin the exact boundary rather than relying on real float drift."""

    async def test_tiny_residual_quantity_is_deleted(self, db_path):
        await execute_trade("AAPL", "buy", 1.0, 100.0)
        # Sell fractionally less than held, leaving a residual just under
        # the epsilon threshold once rounded by the transaction.
        await execute_trade("AAPL", "sell", 1.0 - 1e-10, 100.0)
        assert await get_position("AAPL") is None

    async def test_residual_at_boundary_is_kept(self, db_path):
        await execute_trade("AAPL", "buy", 1.0, 100.0)
        await execute_trade("AAPL", "sell", 1.0 - 1e-6, 100.0)
        position = await get_position("AAPL")
        assert position is not None
        assert position.quantity == pytest.approx(1e-6, abs=1e-9)


class TestTrades:
    async def test_get_trades_most_recent_first(self, db_path):
        await execute_trade("AAPL", "buy", 1, 100.0)
        await execute_trade("GOOGL", "buy", 1, 100.0)
        trades = await get_trades()
        assert [t.ticker for t in trades] == ["GOOGL", "AAPL"]

    async def test_get_trades_respects_limit(self, db_path):
        for _ in range(5):
            await execute_trade("AAPL", "buy", 1, 100.0)
        trades = await get_trades(limit=2)
        assert len(trades) == 2


class TestSnapshots:
    async def test_record_and_get_snapshot(self, db_path):
        snap = await record_snapshot(12345.67)
        assert snap.total_value == 12345.67
        snapshots = await get_snapshots()
        assert len(snapshots) == 1
        assert snapshots[0].id == snap.id

    async def test_snapshots_ordered_oldest_first(self, db_path):
        await record_snapshot(100.0)
        await record_snapshot(200.0)
        await record_snapshot(300.0)
        snapshots = await get_snapshots()
        assert [s.total_value for s in snapshots] == [100.0, 200.0, 300.0]

    async def test_snapshots_since_filter(self, db_path):
        await record_snapshot(100.0)
        mid = await get_snapshots()
        cutoff = mid[-1].recorded_at
        await record_snapshot(200.0)
        recent = await get_snapshots(since=cutoff)
        assert all(s.recorded_at >= cutoff for s in recent)


class TestChatMessages:
    async def test_add_and_get_chat_history(self, db_path):
        await add_chat_message("user", "hello")
        await add_chat_message("assistant", "hi there", actions='{"trades": []}')
        history = await get_chat_history()
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"
        assert history[1].actions == '{"trades": []}'

    async def test_chat_history_respects_limit_and_ordering(self, db_path):
        for i in range(5):
            await add_chat_message("user", f"message {i}")
        history = await get_chat_history(limit=3)
        assert len(history) == 3
        # oldest-first among the most recent 3 -> messages 2, 3, 4
        assert [m.content for m in history] == ["message 2", "message 3", "message 4"]

    async def test_invalid_role_rejected(self, db_path):
        with pytest.raises(InvalidTradeError):
            await add_chat_message("system", "nope")


class TestResetPortfolio:
    async def test_reset_restores_cash(self, db_path):
        await execute_trade("AAPL", "buy", 10, 100.0)
        await reset_portfolio()
        assert await get_cash_balance() == 10000.0

    async def test_reset_clears_positions_trades_snapshots_chat(self, db_path):
        await execute_trade("AAPL", "buy", 10, 100.0)
        await record_snapshot(9000.0)
        await add_chat_message("user", "hi")
        await reset_portfolio()
        assert await get_positions() == []
        assert await get_trades() == []
        assert await get_snapshots() == []
        assert await get_chat_history() == []

    async def test_reset_restores_default_watchlist(self, db_path):
        await add_to_watchlist("PYPL")
        await remove_from_watchlist("AAPL")
        await reset_portfolio()
        tickers = {i.ticker for i in await get_watchlist()}
        assert tickers == {
            "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX",
        }
