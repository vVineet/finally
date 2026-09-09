"""Fixtures for the LLM package's tests: an isolated SQLite DB per test
(same pattern as tests/db and tests/api), plus a real `PriceCache` seeded
with a couple of known prices so trade execution has something to price
against.
"""

from __future__ import annotations

import pytest

from app.market import PriceCache


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """A fresh, unseeded SQLite file path for this test."""
    path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    return path


@pytest.fixture
def price_cache(db_path) -> PriceCache:
    cache = PriceCache()
    cache.update("AAPL", 200.0)
    cache.update("TSLA", 250.0)
    return cache


class FakeMarketSource:
    """Minimal MarketDataSource stand-in -- tracks add/remove calls, no
    real background task, no PriceCache writes of its own."""

    def __init__(self) -> None:
        self._tickers: set[str] = set()

    async def start(self, tickers: list[str]) -> None:
        self._tickers = set(tickers)

    async def stop(self) -> None:
        pass

    async def add_ticker(self, ticker: str) -> None:
        self._tickers.add(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self._tickers.discard(ticker)

    def get_tickers(self) -> list[str]:
        return sorted(self._tickers)


@pytest.fixture
def market_source() -> FakeMarketSource:
    return FakeMarketSource()
