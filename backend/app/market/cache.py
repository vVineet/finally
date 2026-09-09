"""Thread-safe in-memory price cache."""

from __future__ import annotations

import time
from collections import deque
from threading import Lock

from .models import PriceUpdate

# PLAN §13.B13/C4: a bounded per-ticker ring buffer of recent ticks, so
# sparklines and the main chart have one server-side history source
# instead of accumulating from SSE since page load (which empties on every
# refresh). 600 ticks at the ~500ms SSE cadence is ~5 minutes.
HISTORY_MAXLEN = 600


class PriceCache:
    """Thread-safe in-memory cache of the latest price for each ticker.

    Writers: SimulatorDataSource or MassiveDataSource (one at a time).
    Readers: SSE streaming endpoint, portfolio valuation, trade execution,
    GET /api/history/{ticker}.
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        # Bounded per-ticker history: deque(maxlen=HISTORY_MAXLEN) evicts
        # its own oldest entry in O(1) once full, so this stays
        # memory-bounded (<= HISTORY_MAXLEN tuples per ticker) without any
        # extra bookkeeping, and appending is O(1) -- negligible next to
        # the dict write update() already does.
        self._history: dict[str, deque[tuple[float, float]]] = {}
        # PLAN §13.A1: the price the ticker was first seen at (process
        # start for seeded tickers, first tick for one added later).
        # `day_change`/`day_change_percent` are computed against this.
        # Reset only by remove() -- a re-added ticker gets a fresh one.
        self._open_prices: dict[str, float] = {}
        self._lock = Lock()
        self._version: int = 0  # Monotonically increasing; bumped on every update

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record a new price for a ticker. Returns the created PriceUpdate.

        Automatically computes direction and change from the previous price.
        If this is the first update for the ticker, previous_price == price (direction='flat').

        Also appends (timestamp, price) to that ticker's bounded history
        ring buffer (see `get_history`), and, on the very first tick seen
        for this ticker (since construction or since its last `remove()`),
        captures `price` as its `open_price` (see `PriceUpdate.open_price`).
        """
        with self._lock:
            ts = timestamp or time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price
            rounded_price = round(price, 2)

            open_price = self._open_prices.get(ticker)
            if open_price is None:
                open_price = rounded_price
                self._open_prices[ticker] = open_price

            update = PriceUpdate(
                ticker=ticker,
                price=rounded_price,
                previous_price=round(previous_price, 2),
                timestamp=ts,
                open_price=open_price,
            )
            self._prices[ticker] = update

            history = self._history.get(ticker)
            if history is None:
                history = deque(maxlen=HISTORY_MAXLEN)
                self._history[ticker] = history
            history.append((ts, update.price))

            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        """Get the latest price for a single ticker, or None if unknown."""
        with self._lock:
            return self._prices.get(ticker)

    def get_all(self) -> dict[str, PriceUpdate]:
        """Snapshot of all current prices. Returns a shallow copy."""
        with self._lock:
            return dict(self._prices)

    def get_price(self, ticker: str) -> float | None:
        """Convenience: get just the price float, or None."""
        update = self.get(ticker)
        return update.price if update else None

    def get_history(self, ticker: str, limit: int = HISTORY_MAXLEN) -> list[tuple[float, float]]:
        """Recent (timestamp, price) ticks for a ticker, oldest first.

        Returns at most `limit` points (capped at HISTORY_MAXLEN, since
        that's all that's ever retained) -- the most recent `limit` ticks
        if there are more than that buffered. Returns `[]` for a ticker
        with no history yet (unknown ticker, or one just added that hasn't
        ticked); this is a normal, expected state, not an error.
        """
        with self._lock:
            history = self._history.get(ticker)
            if not history:
                return []
            capped = min(limit, len(history))
            if capped <= 0:
                return []
            # deque doesn't support slicing directly; materializing is
            # O(len(history)) <= O(HISTORY_MAXLEN) = O(600), fine for a
            # REST read (not the SSE hot path).
            return list(history)[-capped:]

    def remove(self, ticker: str) -> None:
        """Remove a ticker from the cache (e.g., when removed from watchlist).

        Also evicts its history ring buffer and its open price -- a
        re-added ticker captures a fresh open price on its next tick,
        rather than resuming the old one (PLAN §13.A1).
        """
        with self._lock:
            self._prices.pop(ticker, None)
            self._history.pop(ticker, None)
            self._open_prices.pop(ticker, None)

    @property
    def version(self) -> int:
        """Current version counter. Useful for SSE change detection."""
        return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
