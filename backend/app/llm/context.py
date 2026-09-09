"""Portfolio/watchlist context for the LLM prompt (PLAN §9 step 1).

Richer than the `GET /api/watchlist` REST shape (which omits price per
C3) -- this is prompt content the model reads, never a response body the
frontend parses, so including live prices here is fine and useful.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.db import DEFAULT_USER_ID, get_positions, get_user_profile, get_watchlist
from app.market import PriceCache
from app.portfolio import build_position_view, compute_total_value
from app.portfolio.valuation import PositionView


@dataclass(frozen=True, slots=True)
class WatchlistLine:
    ticker: str
    current_price: float | None


@dataclass(frozen=True, slots=True)
class PortfolioContext:
    cash_balance: float
    total_value: float
    positions: list[PositionView]
    watchlist: list[WatchlistLine]


async def build_portfolio_context(
    price_cache: PriceCache,
    user_id: str = DEFAULT_USER_ID,
) -> PortfolioContext:
    profile = await get_user_profile(user_id)
    positions = await get_positions(user_id)
    watchlist = await get_watchlist(user_id)

    position_views = [build_position_view(p, price_cache) for p in positions]
    total_value = compute_total_value(profile.cash_balance, positions, price_cache)
    watchlist_lines = [
        WatchlistLine(ticker=w.ticker, current_price=price_cache.get_price(w.ticker))
        for w in watchlist
    ]
    return PortfolioContext(
        cash_balance=profile.cash_balance,
        total_value=total_value,
        positions=position_views,
        watchlist=watchlist_lines,
    )


def to_prompt_text(context: PortfolioContext) -> str:
    lines = [
        f"Cash balance: ${context.cash_balance:,.2f}",
        f"Total portfolio value: ${context.total_value:,.2f}",
        "",
        "Positions:" if context.positions else "Positions: none",
    ]
    for p in context.positions:
        price = f"${p.current_price:,.2f}" if p.current_price is not None else "no live price yet"
        pnl = (
            f"${p.unrealized_pnl:,.2f} ({p.unrealized_pnl_percent:+.2f}%)"
            if p.unrealized_pnl is not None
            else "n/a"
        )
        lines.append(
            f"  {p.ticker}: {p.quantity:g} shares @ avg cost ${p.avg_cost:,.2f}, "
            f"current price {price}, unrealized P&L {pnl}"
        )

    lines.append("")
    lines.append("Watchlist:" if context.watchlist else "Watchlist: empty")
    for w in context.watchlist:
        price = f"${w.current_price:,.2f}" if w.current_price is not None else "no live price yet"
        lines.append(f"  {w.ticker}: {price}")

    return "\n".join(lines)
