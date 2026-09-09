"""Data models for market data."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time."""

    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds
    # PLAN §13.A1: the reference price `day_change`/`day_change_percent`
    # are computed against. Populated by PriceCache from the first tick it
    # ever saw for this ticker (or the first tick after a remove+re-add) --
    # optional/defaulted here so existing call sites that don't know about
    # it (and existing tests) are unaffected.
    open_price: float | None = None

    @property
    def change(self) -> float:
        """Absolute price change from previous update (tick-over-tick)."""
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        """Percentage change from previous update (tick-over-tick)."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat'."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    @property
    def day_change(self) -> float:
        """Absolute change from `open_price` (PLAN §13.A1).

        NOT a true market previous-close delta -- see `open_price`'s
        docstring and planning/API_CONTRACT.md. `0.0` (never an error) if
        there's no open price yet.
        """
        if self.open_price is None:
            return 0.0
        return round(self.price - self.open_price, 4)

    @property
    def day_change_percent(self) -> float:
        """Percentage change from `open_price` (PLAN §13.A1). `0.0` (never
        a ZeroDivisionError/NaN) if there's no open price yet, or it's 0."""
        if not self.open_price:  # covers both None and 0.0
            return 0.0
        return round((self.price - self.open_price) / self.open_price * 100, 4)

    def to_dict(self) -> dict:
        """Serialize for JSON / SSE transmission."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "previous_price": self.previous_price,
            "timestamp": self.timestamp,
            "change": self.change,
            "change_percent": self.change_percent,
            "direction": self.direction,
            "day_change": self.day_change,
            "day_change_percent": self.day_change_percent,
        }
