"""Total value and per-position P&L math.

Binding decision B6: total_value is defined exactly once, here, and every
caller (GET /api/portfolio, POST /api/portfolio/trade, POST
/api/portfolio/reset, the snapshot background task, the post-trade
snapshot) goes through `compute_total_value`. Tickers with no cached price
are excluded from the sum rather than valued at zero or avg_cost, per B6.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.db import Position
from app.market import PriceCache


def compute_total_value(
    cash_balance: float,
    positions: list[Position],
    price_cache: PriceCache,
) -> float:
    """total_value = cash_balance + sum(quantity * current_price).

    Positions whose ticker has no entry in the price cache yet (e.g. just
    bought, before the market source has ticked it) are excluded from the
    sum entirely -- not valued at 0, not valued at avg_cost.
    """
    total = cash_balance
    for position in positions:
        price = price_cache.get_price(position.ticker)
        if price is not None:
            total += position.quantity * price
    return round(total, 2)


@dataclass(frozen=True, slots=True)
class PositionView:
    """A position enriched with live price and P&L, for API responses.

    `current_price`, `market_value`, `unrealized_pnl`, and
    `unrealized_pnl_percent` are `None` when the price cache has no entry
    for the ticker yet -- never 0, which would be indistinguishable from a
    real value.
    """

    ticker: str
    quantity: float
    avg_cost: float
    current_price: float | None
    market_value: float | None
    unrealized_pnl: float | None
    unrealized_pnl_percent: float | None
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "quantity": self.quantity,
            "avg_cost": self.avg_cost,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_percent": self.unrealized_pnl_percent,
            "updated_at": self.updated_at,
        }


def build_position_view(position: Position, price_cache: PriceCache) -> PositionView:
    """Enrich a single Position with its current price and P&L."""
    current_price = price_cache.get_price(position.ticker)
    if current_price is None:
        return PositionView(
            ticker=position.ticker,
            quantity=position.quantity,
            avg_cost=position.avg_cost,
            current_price=None,
            market_value=None,
            unrealized_pnl=None,
            unrealized_pnl_percent=None,
            updated_at=position.updated_at,
        )

    market_value = round(position.quantity * current_price, 2)
    cost_basis = position.quantity * position.avg_cost
    unrealized_pnl = round(market_value - cost_basis, 2)
    unrealized_pnl_percent = round((unrealized_pnl / cost_basis) * 100, 4) if cost_basis else 0.0

    return PositionView(
        ticker=position.ticker,
        quantity=position.quantity,
        avg_cost=position.avg_cost,
        current_price=current_price,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_percent=unrealized_pnl_percent,
        updated_at=position.updated_at,
    )
