"""Portfolio value snapshotting.

Per PLAN §7, a row is recorded every 30 seconds by a background task, and
immediately after each trade execution. Both paths go through
`snapshot_once` so there is exactly one way total_value is computed and
persisted.
"""

from __future__ import annotations

import asyncio
import logging

from app.db import (
    DEFAULT_USER_ID,
    PortfolioSnapshot,
    get_positions,
    get_user_profile,
    record_snapshot,
)
from app.market import PriceCache

from .valuation import compute_total_value

logger = logging.getLogger(__name__)

DEFAULT_SNAPSHOT_INTERVAL_SECONDS = 30.0


async def snapshot_once(
    price_cache: PriceCache,
    user_id: str = DEFAULT_USER_ID,
) -> PortfolioSnapshot:
    """Compute total_value right now and persist one snapshot row."""
    profile = await get_user_profile(user_id)
    positions = await get_positions(user_id)
    total_value = compute_total_value(profile.cash_balance, positions, price_cache)
    return await record_snapshot(total_value, user_id)


async def snapshot_loop(
    price_cache: PriceCache,
    interval: float = DEFAULT_SNAPSHOT_INTERVAL_SECONDS,
    user_id: str = DEFAULT_USER_ID,
) -> None:
    """Background task: record a snapshot every `interval` seconds forever.

    Runs until cancelled (the caller is expected to `asyncio.create_task`
    this and cancel it on shutdown). A failure recording one snapshot is
    logged and does not kill the loop.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            await snapshot_once(price_cache, user_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed to record portfolio snapshot")
