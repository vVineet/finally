"""Tracked-ticker set and MarketDataSource reconciliation (PLAN §13.A4).

Binding decision A4: tracked tickers = watchlist UNION tickers with a
non-zero position. Watchlist mutations (and trades, which can open a
position in a ticker not on the watchlist) must call through to
`MarketDataSource.add_ticker()` / `remove_ticker()` so pricing stays in
sync. Never stop pricing a ticker the user still holds.
"""

from __future__ import annotations

from app.db import DEFAULT_USER_ID, get_positions, get_watchlist
from app.market import MarketDataSource

_POSITION_EPSILON = 1e-9


async def get_tracked_tickers(user_id: str = DEFAULT_USER_ID) -> set[str]:
    """watchlist tickers union tickers with a non-zero position."""
    watchlist = await get_watchlist(user_id)
    positions = await get_positions(user_id)
    tickers = {item.ticker for item in watchlist}
    tickers |= {p.ticker for p in positions if abs(p.quantity) > _POSITION_EPSILON}
    return tickers


async def sync_tracked_tickers(
    source: MarketDataSource,
    user_id: str = DEFAULT_USER_ID,
) -> None:
    """Reconcile the market data source's active tickers with A4's set.

    Adds any ticker in the desired set the source isn't already tracking,
    and removes any ticker the source is tracking that is neither
    watchlisted nor held. Safe to call after every watchlist mutation and
    every trade -- both `add_ticker` and `remove_ticker` are documented
    no-ops when already in the desired state.
    """
    desired = await get_tracked_tickers(user_id)
    current = set(source.get_tickers())

    for ticker in desired - current:
        await source.add_ticker(ticker)
    for ticker in current - desired:
        await source.remove_ticker(ticker)
