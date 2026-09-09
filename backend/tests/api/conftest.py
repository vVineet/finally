"""Fixtures for API route tests.

Most tests hit routes directly via `TestClient(app)` *without* entering it
as a context manager, so FastAPI's `lifespan` never runs -- no real
background market data task, no real snapshot loop. `app.db` still works
because it lazily initializes/seeds on first connection (per-test isolated
DB via the `db_path` fixture, same pattern as tests/db/conftest.py).
`price_cache` and `market_source` are supplied as fakes via
`dependency_overrides` so trade/watchlist/reset endpoints are fully
testable without any real market data source.

One dedicated test (test_static_mount.py) exercises the real lifespan via
`with TestClient(app) as client:` to prove startup/shutdown wiring works
end to end.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_market_source, get_price_cache
from app.main import create_app
from app.market import PriceCache


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """A fresh, unseeded SQLite file path for this test."""
    path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    return path


class FakeMarketSource:
    """A MarketDataSource stand-in that just tracks which tickers it was
    told to add/remove, with no real background task and no PriceCache
    writes of its own (tests seed the PriceCache directly)."""

    def __init__(self) -> None:
        self._tickers: set[str] = set()
        self.started_with: list[str] | None = None
        self.stopped = False

    async def start(self, tickers: list[str]) -> None:
        self.started_with = list(tickers)
        self._tickers = set(tickers)

    async def stop(self) -> None:
        self.stopped = True

    async def add_ticker(self, ticker: str) -> None:
        self._tickers.add(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self._tickers.discard(ticker)

    def get_tickers(self) -> list[str]:
        return sorted(self._tickers)


@pytest.fixture
def price_cache() -> PriceCache:
    return PriceCache()


@pytest.fixture
def market_source() -> FakeMarketSource:
    return FakeMarketSource()


@pytest.fixture
def app(db_path, price_cache, market_source):
    application = create_app(static_dir=None)
    application.dependency_overrides[get_price_cache] = lambda: price_cache
    application.dependency_overrides[get_market_source] = lambda: market_source
    return application


@pytest.fixture
def client(app):
    return TestClient(app)
