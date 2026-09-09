"""Concurrency tests for the BEGIN IMMEDIATE trade transaction (PLAN §13.B9).

These exercise the module-private `_execute_trade_sync` directly from real
OS threads (not asyncio.to_thread) so we control exactly how many trades
race against each other, independent of the size of the default event-loop
threadpool.
"""

from __future__ import annotations

import threading

from app.db.errors import InsufficientSharesError
from app.db.repository import _execute_trade_sync, _get_position_sync, _get_user_profile_sync


class TestConcurrentBuys:
    def test_concurrent_buys_do_not_lose_updates(self, db_path):
        """N threads each buy 1 share at $10 simultaneously. Without the
        BEGIN IMMEDIATE lock around the cash+position read-modify-write,
        concurrent threads can both read the same starting cash_balance and
        each independently compute cash - 10, losing one of the debits
        (the classic check-then-act race named in B9)."""
        n_threads = 20
        barrier = threading.Barrier(n_threads)
        errors: list[Exception] = []

        def buy_one():
            barrier.wait()
            try:
                _execute_trade_sync("AAPL", "buy", 1, 10.0, "default", None)
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=buy_one) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"unexpected errors: {errors}"

        profile = _get_user_profile_sync("default", None)
        position = _get_position_sync("AAPL", "default", None)

        assert position is not None
        assert position.quantity == n_threads
        assert profile.cash_balance == 10000.0 - n_threads * 10.0

    def test_concurrent_buys_never_overdraw_cash(self, db_path):
        """Each thread tries to buy shares costing slightly more than 1/10
        of the starting cash. Only 10 of ~15 concurrent attempts can ever
        succeed; none may succeed if doing so would drive cash negative."""
        n_threads = 15
        cost_per_buy = 1000.0  # 10 succeeding buys exhaust the $10,000 cash
        barrier = threading.Barrier(n_threads)
        results: list[str] = []
        lock = threading.Lock()

        def attempt_buy():
            barrier.wait()
            try:
                _execute_trade_sync("AAPL", "buy", 1, cost_per_buy, "default", None)
                with lock:
                    results.append("ok")
            except Exception:
                with lock:
                    results.append("rejected")

        threads = [threading.Thread(target=attempt_buy) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        profile = _get_user_profile_sync("default", None)
        assert profile.cash_balance >= 0
        assert results.count("ok") <= 10


class TestConcurrentSells:
    def test_concurrent_sells_cannot_oversell(self, db_path):
        """Ten shares held; two threads race to each sell 6. Only one may
        succeed (there are not 12 shares to sell) — the BEGIN IMMEDIATE
        lock must serialize them so the second thread sees the
        already-reduced quantity, not the stale value of 10."""
        _execute_trade_sync("AAPL", "buy", 10, 100.0, "default", None)

        barrier = threading.Barrier(2)
        outcomes: list[str] = []
        lock = threading.Lock()

        def attempt_sell():
            barrier.wait()
            try:
                _execute_trade_sync("AAPL", "sell", 6, 100.0, "default", None)
                with lock:
                    outcomes.append("ok")
            except InsufficientSharesError:
                with lock:
                    outcomes.append("rejected")

        threads = [threading.Thread(target=attempt_sell) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert sorted(outcomes) == ["ok", "rejected"]
        position = _get_position_sync("AAPL", "default", None)
        assert position is not None
        assert position.quantity == 4
