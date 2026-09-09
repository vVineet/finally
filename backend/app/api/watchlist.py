"""Watchlist endpoints: GET/POST /api/watchlist, DELETE /api/watchlist/{ticker}.

C3: responses contain tickers + metadata only, never prices -- SSE
(`/api/stream/prices`) owns price. A4: every mutation calls through to
`sync_tracked_tickers` so the market data source starts/stops pricing the
ticker as appropriate (never dropping one still held).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.db import add_to_watchlist, get_watchlist, remove_from_watchlist
from app.market import MarketDataSource
from app.portfolio import sync_tracked_tickers

from .deps import get_market_source
from .errors import normalize_ticker
from .schemas import WatchlistAddRequest

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


async def _watchlist_response() -> dict:
    items = await get_watchlist()
    return {"watchlist": [{"ticker": w.ticker, "added_at": w.added_at} for w in items]}


@router.get("")
async def list_watchlist() -> dict:
    return await _watchlist_response()


@router.post("")
async def add_ticker(
    body: WatchlistAddRequest,
    market_source: MarketDataSource = Depends(get_market_source),
) -> dict:
    ticker = normalize_ticker(body.ticker)
    await add_to_watchlist(ticker)
    await sync_tracked_tickers(market_source)
    return await _watchlist_response()


@router.delete("/{ticker}")
async def remove_ticker(
    ticker: str,
    market_source: MarketDataSource = Depends(get_market_source),
) -> dict:
    normalized = normalize_ticker(ticker)
    removed = await remove_from_watchlist(normalized)
    if not removed:
        raise HTTPException(status_code=404, detail=f"{normalized} is not on the watchlist")
    await sync_tracked_tickers(market_source)
    return await _watchlist_response()
