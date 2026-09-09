"""FastAPI dependency accessors for app-wide singletons.

`price_cache` and `market_source` are created once in `app.main`'s lifespan
and stashed on `app.state`. Routes pull them via `Depends(get_price_cache)`
/ `Depends(get_market_source)` rather than importing globals, so tests can
swap in fakes with `app.dependency_overrides` without needing the real
market data background task running.
"""

from __future__ import annotations

from fastapi import Request

from app.market import MarketDataSource, PriceCache


def get_price_cache(request: Request) -> PriceCache:
    return request.app.state.price_cache


def get_market_source(request: Request) -> MarketDataSource:
    return request.app.state.market_source
