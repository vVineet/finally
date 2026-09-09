"""Execute the model's proposed trades/watchlist changes through the SAME
validated paths as a manual trade (planning/LLM_DESIGN.md §3, PLAN §13.A3
reuse requirement). Never reimplements validation -- every check here
either delegates to `app.db`/`app.api.errors` or mirrors a check that
already lives in `app.api.portfolio` for the identical reason (B4: the
price-cache lookup has to happen at this layer since `app.db` never
imports `app.market`).
"""

from __future__ import annotations

import math

from fastapi import HTTPException

from app.db import DBError, add_to_watchlist, execute_trade, remove_from_watchlist
from app.market import PriceCache

from .schema import LLMTrade, LLMWatchlistChange

# Deferred import (inside the functions below, not at module level): `app.llm`
# is imported by `app.api.chat`, so importing `app.api.errors` here at module
# level would import the `app.api` package (running its __init__, which
# imports `chat`, which imports `app.llm` -- a circular import back into this
# still-initializing package). Importing it lazily, once both packages have
# finished loading, reuses the exact same function without restructuring
# either package.

NO_PRICE_ERROR = (
    "No live price available for {ticker} yet; add it to the watchlist and wait "
    "for the next tick before trading it"
)
BAD_QUANTITY_ERROR = "quantity must be a positive, finite number"


async def execute_trades(
    trades: list[LLMTrade],
    price_cache: PriceCache,
) -> tuple[list[dict], list[dict]]:
    """Returns (trades_executed, trades_failed), both API_CONTRACT.md-shaped."""
    from app.api.errors import normalize_ticker

    executed: list[dict] = []
    failed: list[dict] = []

    for t in trades:
        try:
            ticker = normalize_ticker(t.ticker)
        except HTTPException as exc:
            failed.append(
                {
                    "ticker": t.ticker,
                    "side": t.side,
                    "quantity": t.quantity,
                    "status": "failed",
                    "error": str(exc.detail),
                }
            )
            continue

        if not math.isfinite(t.quantity) or t.quantity <= 0:
            failed.append(
                {
                    "ticker": ticker,
                    "side": t.side,
                    "quantity": t.quantity,
                    "status": "failed",
                    "error": BAD_QUANTITY_ERROR,
                }
            )
            continue

        price = price_cache.get_price(ticker)
        if price is None:
            failed.append(
                {
                    "ticker": ticker,
                    "side": t.side,
                    "quantity": t.quantity,
                    "status": "failed",
                    "error": NO_PRICE_ERROR.format(ticker=ticker),
                }
            )
            continue

        try:
            result = await execute_trade(ticker=ticker, side=t.side, quantity=t.quantity, price=price)
        except DBError as exc:
            failed.append(
                {
                    "ticker": ticker,
                    "side": t.side,
                    "quantity": t.quantity,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            continue

        # B4: trading a ticker not on the watchlist auto-adds it, same as
        # the manual trade endpoint.
        await add_to_watchlist(ticker)
        executed.append(
            {
                "ticker": ticker,
                "side": result.trade.side,
                "quantity": result.trade.quantity,
                "price": result.trade.price,
                "status": "success",
            }
        )

    return executed, failed


async def execute_watchlist_changes(changes: list[LLMWatchlistChange]) -> list[dict]:
    """Returns a single list mixing success/failure entries (API_CONTRACT.md
    doesn't split watchlist_changes into two arrays the way trades are
    split)."""
    from app.api.errors import normalize_ticker

    results: list[dict] = []

    for c in changes:
        try:
            ticker = normalize_ticker(c.ticker)
        except HTTPException as exc:
            results.append(
                {"ticker": c.ticker, "action": c.action, "status": "failed", "error": str(exc.detail)}
            )
            continue

        if c.action == "add":
            await add_to_watchlist(ticker)
            results.append({"ticker": ticker, "action": "add", "status": "success"})
        else:
            removed = await remove_from_watchlist(ticker)
            if removed:
                results.append({"ticker": ticker, "action": "remove", "status": "success"})
            else:
                results.append(
                    {
                        "ticker": ticker,
                        "action": "remove",
                        "status": "failed",
                        "error": f"{ticker} is not on the watchlist",
                    }
                )

    return results
