"""Domain models for the database layer.

Frozen, slotted dataclasses mirroring the six tables in schema.py, plus
TradeResult, the composite return value of execute_trade().
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserProfile:
    """A single user's account state (cash balance)."""

    id: str
    cash_balance: float
    created_at: str


@dataclass(frozen=True, slots=True)
class WatchlistItem:
    """A ticker the user is watching."""

    id: str
    user_id: str
    ticker: str
    added_at: str


@dataclass(frozen=True, slots=True)
class Position:
    """A held quantity of a ticker with its cost basis."""

    id: str
    user_id: str
    ticker: str
    quantity: float
    avg_cost: float
    updated_at: str


@dataclass(frozen=True, slots=True)
class Trade:
    """One row of the append-only trade history."""

    id: str
    user_id: str
    ticker: str
    side: str  # "buy" | "sell"
    quantity: float
    price: float
    executed_at: str


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """Total portfolio value at a point in time (for the P&L chart)."""

    id: str
    user_id: str
    total_value: float
    recorded_at: str


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One message in the conversation history with the LLM."""

    id: str
    user_id: str
    role: str  # "user" | "assistant"
    content: str
    actions: str | None  # pre-serialized JSON, or None
    created_at: str


@dataclass(frozen=True, slots=True)
class TradeResult:
    """Outcome of a successfully executed trade."""

    trade: Trade
    position: Position | None  # None if the position was closed/deleted
    cash_balance: float
