from __future__ import annotations

import pytest

from app.db import add_to_watchlist, execute_trade, remove_from_watchlist
from app.portfolio import get_tracked_tickers, sync_tracked_tickers


class FakeMarketSource:
    def __init__(self, initial: set[str] | None = None) -> None:
        self._tickers: set[str] = set(initial or ())
        self.added: list[str] = []
        self.removed: list[str] = []

    async def start(self, tickers):
        self._tickers = set(tickers)

    async def stop(self):
        pass

    async def add_ticker(self, ticker: str) -> None:
        self._tickers.add(ticker)
        self.added.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self._tickers.discard(ticker)
        self.removed.append(ticker)

    def get_tickers(self) -> list[str]:
        return sorted(self._tickers)


@pytest.mark.usefixtures("db_path")
async def test_get_tracked_tickers_is_watchlist_by_default():
    tickers = await get_tracked_tickers()
    assert tickers == {
        "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX",
    }


@pytest.mark.usefixtures("db_path")
async def test_get_tracked_tickers_includes_held_positions_not_on_watchlist():
    await remove_from_watchlist("AAPL")
    await execute_trade(ticker="AAPL", side="buy", quantity=1, price=100.0)

    tickers = await get_tracked_tickers()

    assert "AAPL" in tickers  # still tracked because it's held


@pytest.mark.usefixtures("db_path")
async def test_get_tracked_tickers_excludes_closed_position_not_on_watchlist():
    await remove_from_watchlist("AAPL")
    await execute_trade(ticker="AAPL", side="buy", quantity=1, price=100.0)
    await execute_trade(ticker="AAPL", side="sell", quantity=1, price=110.0)

    tickers = await get_tracked_tickers()

    assert "AAPL" not in tickers


@pytest.mark.usefixtures("db_path")
async def test_sync_tracked_tickers_adds_missing_and_removes_extra():
    source = FakeMarketSource(initial={"OLD"})

    await sync_tracked_tickers(source)

    assert "OLD" not in source.get_tickers()
    assert "AAPL" in source.get_tickers()
    assert set(source.get_tickers()) == await get_tracked_tickers()


@pytest.mark.usefixtures("db_path")
async def test_sync_tracked_tickers_never_drops_a_held_ticker():
    await remove_from_watchlist("TSLA")
    await execute_trade(ticker="TSLA", side="buy", quantity=2, price=250.0)
    source = FakeMarketSource(initial=set())

    await sync_tracked_tickers(source)

    assert "TSLA" in source.get_tickers()


@pytest.mark.usefixtures("db_path")
async def test_watchlist_add_is_idempotent_for_tracking():
    source = FakeMarketSource()
    await add_to_watchlist("PYPL")
    await sync_tracked_tickers(source)
    assert "PYPL" in source.get_tickers()
