"""Portfolio endpoints: GET /api/portfolio, POST /api/portfolio/trade,
GET /api/portfolio/history, POST /api/portfolio/reset.

See planning/API_CONTRACT.md for the exact response shapes.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import (
    DEFAULT_USER_ID,
    Position,
    add_to_watchlist,
    execute_trade,
    get_positions,
    get_snapshots,
    get_user_profile,
    get_watchlist,
    reset_portfolio,
)
from app.market import MarketDataSource, PriceCache
from app.portfolio import (
    build_position_view,
    compute_total_value,
    snapshot_once,
    sync_tracked_tickers,
)

from .deps import get_market_source, get_price_cache
from .errors import normalize_ticker
from .schemas import TradeRequest

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

MAX_HISTORY_LIMIT = 2000
DEFAULT_HISTORY_LIMIT = 200
MAX_TRADES_LIMIT = 1000


async def _positions_dict(positions: list[Position], price_cache: PriceCache) -> list[dict]:
    return [build_position_view(p, price_cache).to_dict() for p in positions]


async def build_portfolio_response(price_cache: PriceCache, user_id: str = DEFAULT_USER_ID) -> dict:
    """The single response shape for "current portfolio state", shared by
    GET /api/portfolio and every mutating endpoint that returns updated
    state per PLAN §13.C2."""
    profile = await get_user_profile(user_id)
    positions = await get_positions(user_id)
    total_value = compute_total_value(profile.cash_balance, positions, price_cache)
    return {
        "cash_balance": profile.cash_balance,
        "total_value": total_value,
        "positions": await _positions_dict(positions, price_cache),
        "updated_at": datetime.now(UTC).isoformat(),
    }


@router.get("")
async def get_portfolio(price_cache: PriceCache = Depends(get_price_cache)) -> dict:
    return await build_portfolio_response(price_cache)


@router.post("/trade")
async def trade(
    body: TradeRequest,
    price_cache: PriceCache = Depends(get_price_cache),
    market_source: MarketDataSource = Depends(get_market_source),
) -> dict:
    ticker = normalize_ticker(body.ticker)

    # B4: reject non-finite/non-positive quantity before ever touching the
    # DB or the price cache.
    if not math.isfinite(body.quantity) or body.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be a positive, finite number")

    # B4: reject a trade when the price cache has no entry for the ticker
    # yet, rather than filling at 0/None. app.db.execute_trade never sees
    # the cache, so this check belongs here.
    price = price_cache.get_price(ticker)
    if price is None:
        raise HTTPException(
            status_code=400,
            detail=f"No live price available for {ticker} yet; add it to the watchlist and wait "
            "for the next tick before trading it",
        )

    # DBError subclasses (InvalidTradeError/InsufficientCashError/
    # InsufficientSharesError) propagate to the handlers in app.api.errors.
    result = await execute_trade(ticker=ticker, side=body.side, quantity=body.quantity, price=price)

    # B4: trading a ticker not on the watchlist auto-adds it.
    await add_to_watchlist(ticker)
    # A4: keep the market source in sync now that the watchlist/positions
    # may have changed (new ticker added, or a position fully closed).
    await sync_tracked_tickers(market_source)

    # Snapshot immediately after each trade (PLAN §7).
    await snapshot_once(price_cache)

    portfolio = await build_portfolio_response(price_cache)
    return {
        "trade": {
            "id": result.trade.id,
            "ticker": result.trade.ticker,
            "side": result.trade.side,
            "quantity": result.trade.quantity,
            "price": result.trade.price,
            "executed_at": result.trade.executed_at,
        },
        "portfolio": portfolio,
    }


@router.get("/history")
async def portfolio_history(
    since: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
) -> dict:
    if since is not None:
        try:
            datetime.fromisoformat(since)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"since must be an ISO 8601 timestamp, got {since!r}"
            ) from exc

    snapshots = await get_snapshots(since=since, limit=limit)
    return {
        "snapshots": [
            {"total_value": s.total_value, "recorded_at": s.recorded_at} for s in snapshots
        ]
    }


@router.post("/reset")
async def reset(
    price_cache: PriceCache = Depends(get_price_cache),
    market_source: MarketDataSource = Depends(get_market_source),
) -> dict:
    await reset_portfolio()
    await sync_tracked_tickers(market_source)
    await snapshot_once(price_cache)

    portfolio = await build_portfolio_response(price_cache)
    watchlist = await get_watchlist()
    return {
        "portfolio": portfolio,
        "watchlist": [{"ticker": w.ticker, "added_at": w.added_at} for w in watchlist],
    }
