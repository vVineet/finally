"""Portfolio valuation, tracking, and snapshotting logic.

`app/db/` deliberately has no dependency on `app/market/` (see
planning/DATABASE_SUMMARY.md's "What the Backend API Engineer must
supply"). This package is the seam that joins the two: it reads prices out
of a `PriceCache` and combines them with `app/db` positions/cash to answer
"what is this portfolio worth" (PLAN §13.B6), decides which tickers the
market data source should be actively pricing (§13.A4), and runs the
periodic + post-trade snapshot writes (§7, §13.B2).

Public API:
    compute_total_value       - the one definition of total_value (B6)
    build_position_view       - per-position P&L view for GET /api/portfolio
    PositionView              - its return type
    get_tracked_tickers       - watchlist union non-zero positions (A4)
    sync_tracked_tickers      - reconcile a MarketDataSource against it
    snapshot_once             - compute + persist one portfolio_snapshots row
    snapshot_loop             - background task: snapshot_once every interval
"""

from .snapshotter import snapshot_loop, snapshot_once
from .tracking import get_tracked_tickers, sync_tracked_tickers
from .valuation import PositionView, build_position_view, compute_total_value

__all__ = [
    "compute_total_value",
    "build_position_view",
    "PositionView",
    "get_tracked_tickers",
    "sync_tracked_tickers",
    "snapshot_once",
    "snapshot_loop",
]
