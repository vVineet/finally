from __future__ import annotations

import asyncio
import contextlib

import pytest

from app.db import execute_trade, get_snapshots
from app.market import PriceCache
from app.portfolio import snapshot_loop, snapshot_once


@pytest.mark.usefixtures("db_path")
async def test_snapshot_once_records_current_total_value():
    cache = PriceCache()
    cache.update("AAPL", 200.0)
    await execute_trade(ticker="AAPL", side="buy", quantity=10, price=200.0)

    snapshot = await snapshot_once(cache)

    # cash: 10000 - 2000 = 8000; positions: 10*200 = 2000 -> 10000
    assert snapshot.total_value == 10000.0
    snapshots = await get_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].total_value == 10000.0


@pytest.mark.usefixtures("db_path")
async def test_snapshot_loop_runs_periodically_until_cancelled():
    cache = PriceCache()

    task = asyncio.create_task(snapshot_loop(cache, interval=0.01))
    try:
        # Poll for up to ~2s rather than a single fixed sleep -- a fixed
        # sleep/interval ratio is flaky under slower execution (e.g. with
        # coverage instrumentation), where fewer loop iterations complete
        # in the same wall-clock window.
        for _ in range(200):
            if len(await get_snapshots()) >= 2:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("snapshot_loop did not record 2 snapshots in time")
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    snapshots = await get_snapshots()
    assert len(snapshots) >= 2
