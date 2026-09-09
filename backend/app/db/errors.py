"""Exceptions raised by the database layer.

The repository never returns an error sentinel — callers catch these.
"""

from __future__ import annotations


class DBError(Exception):
    """Base class for all database-layer errors."""


class InvalidTradeError(DBError):
    """Raised for structurally invalid trade requests.

    Covers non-finite/non-positive quantity or price, and side values other
    than "buy" or "sell".
    """


class InsufficientCashError(DBError):
    """Raised when a buy would overdraw the cash balance."""

    def __init__(self, required: float, available: float) -> None:
        self.required = required
        self.available = available
        super().__init__(f"Insufficient cash: required {required:.2f}, available {available:.2f}")


class InsufficientSharesError(DBError):
    """Raised when a sell exceeds the held quantity (beyond float tolerance)."""

    def __init__(self, requested: float, held: float) -> None:
        self.requested = requested
        self.held = held
        super().__init__(f"Insufficient shares: requested {requested}, held {held}")
