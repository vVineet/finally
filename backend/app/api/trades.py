"""GET /api/trades -- the trade blotter (PLAN §13.B1)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.db import get_trades

router = APIRouter(prefix="/api/trades", tags=["trades"])

DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


@router.get("")
async def list_trades(limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)) -> dict:
    trades = await get_trades(limit=limit)
    return {
        "trades": [
            {
                "id": t.id,
                "ticker": t.ticker,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "executed_at": t.executed_at,
            }
            for t in trades
        ]
    }
