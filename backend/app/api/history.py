"""GET /api/history/{ticker} -- server-side price history (PLAN §13.B13/C4).

Single source of truth for both sparklines and the main chart, backed by
`PriceCache`'s bounded per-ticker ring buffer (`app/market/cache.py`,
`HISTORY_MAXLEN` ticks -- about 5 minutes at the ~500ms SSE cadence). This
replaces the frontend's accumulate-since-page-load approach, which emptied
on every refresh while the server-persisted P&L chart kept its history.

Exact response contract (do not change without checking with the
Frontend Engineer, who codes against this):

    {
      "ticker": "AAPL",
      "points": [{"t": "2026-09-08T19:42:03.500Z", "price": 190.23}, ...]
    }

- `points` is oldest-first.
- `t` is ISO 8601 UTC with a literal "Z" suffix (millisecond precision) --
  the one deliberate exception to this codebase's usual "+00:00" suffix
  (see planning/API_CONTRACT.md), chosen to match the contract the
  Frontend Engineer is already coding against.
- An unknown/never-ticked ticker returns `200` with `"points": []`, not a
  404 -- a just-added ticker with no history yet is a normal state.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query

from app.market import PriceCache
from app.market.cache import HISTORY_MAXLEN

from .deps import get_price_cache

router = APIRouter(prefix="/api/history", tags=["history"])


def _to_iso_z(timestamp: float) -> str:
    """Epoch seconds -> ISO 8601 UTC with millisecond precision and a "Z"
    suffix, e.g. 1234567890.5 -> "2009-02-13T23:31:30.500Z"."""
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


@router.get("/{ticker}")
async def get_ticker_history(
    ticker: str,
    limit: int = Query(default=HISTORY_MAXLEN, ge=1, le=HISTORY_MAXLEN),
    price_cache: PriceCache = Depends(get_price_cache),
) -> dict:
    normalized = ticker.strip().upper()
    points = price_cache.get_history(normalized, limit=limit)
    return {
        "ticker": normalized,
        "points": [{"t": _to_iso_z(ts), "price": price} for ts, price in points],
    }
