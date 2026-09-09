"""Repository API — the only surface other packages should use to talk to
the database. See planning/DATABASE_DESIGN.md for the full contract.

Every public function is `async def` and dispatches its blocking sqlite3
work to a threadpool via `asyncio.to_thread`, so async request handlers
(and the SSE stream) never stall on DB I/O (PLAN §13.B9). The actual work
lives in module-private `_sync_*` functions, which are also unit-tested
directly (no event loop required) — in particular for the concurrent-trade
test, which must run several of them from real OS threads at once.
"""

from __future__ import annotations

import asyncio
import math
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .connection import DEFAULT_USER_ID, get_connection
from .errors import InsufficientCashError, InsufficientSharesError, InvalidTradeError
from .models import (
    ChatMessage,
    PortfolioSnapshot,
    Position,
    Trade,
    TradeResult,
    UserProfile,
    WatchlistItem,
)
from .seed import DEFAULT_WATCHLIST

_POSITION_EPSILON = 1e-9
_SHARES_EPSILON = 1e-9

__all__ = [
    "DEFAULT_USER_ID",
    "init_db",
    "get_user_profile",
    "get_cash_balance",
    "get_watchlist",
    "add_to_watchlist",
    "remove_from_watchlist",
    "get_positions",
    "get_position",
    "execute_trade",
    "get_trades",
    "record_snapshot",
    "get_snapshots",
    "add_chat_message",
    "get_chat_history",
    "reset_portfolio",
]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


# --------------------------------------------------------------------------
# Row -> dataclass converters
# --------------------------------------------------------------------------


def _row_to_profile(row: sqlite3.Row) -> UserProfile:
    return UserProfile(id=row["id"], cash_balance=row["cash_balance"], created_at=row["created_at"])


def _row_to_watchlist_item(row: sqlite3.Row) -> WatchlistItem:
    return WatchlistItem(
        id=row["id"], user_id=row["user_id"], ticker=row["ticker"], added_at=row["added_at"]
    )


def _row_to_position(row: sqlite3.Row) -> Position:
    return Position(
        id=row["id"],
        user_id=row["user_id"],
        ticker=row["ticker"],
        quantity=row["quantity"],
        avg_cost=row["avg_cost"],
        updated_at=row["updated_at"],
    )


def _row_to_trade(row: sqlite3.Row) -> Trade:
    return Trade(
        id=row["id"],
        user_id=row["user_id"],
        ticker=row["ticker"],
        side=row["side"],
        quantity=row["quantity"],
        price=row["price"],
        executed_at=row["executed_at"],
    )


def _row_to_snapshot(row: sqlite3.Row) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        id=row["id"],
        user_id=row["user_id"],
        total_value=row["total_value"],
        recorded_at=row["recorded_at"],
    )


def _row_to_chat_message(row: sqlite3.Row) -> ChatMessage:
    return ChatMessage(
        id=row["id"],
        user_id=row["user_id"],
        role=row["role"],
        content=row["content"],
        actions=row["actions"],
        created_at=row["created_at"],
    )


# --------------------------------------------------------------------------
# Sync implementations (run inside the threadpool)
# --------------------------------------------------------------------------


def _init_db_sync(db_path: Path | None) -> None:
    with get_connection(db_path):
        pass  # opening the connection is enough to trigger lazy init


def _get_user_profile_sync(user_id: str, db_path: Path | None) -> UserProfile:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT id, cash_balance, created_at FROM users_profile WHERE id = ?", (user_id,)
        ).fetchone()
        return _row_to_profile(row)


def _get_cash_balance_sync(user_id: str, db_path: Path | None) -> float:
    return _get_user_profile_sync(user_id, db_path).cash_balance


def _get_watchlist_sync(user_id: str, db_path: Path | None) -> list[WatchlistItem]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id, user_id, ticker, added_at FROM watchlist "
            "WHERE user_id = ? ORDER BY added_at ASC",
            (user_id,),
        ).fetchall()
        return [_row_to_watchlist_item(r) for r in rows]


def _add_to_watchlist_sync(ticker: str, user_id: str, db_path: Path | None) -> WatchlistItem:
    normalized = _normalize_ticker(ticker)
    with get_connection(db_path) as conn:
        existing = conn.execute(
            "SELECT id, user_id, ticker, added_at FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, normalized),
        ).fetchone()
        if existing is not None:
            return _row_to_watchlist_item(existing)
        new_id = str(uuid4())
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (new_id, user_id, normalized, _now()),
        )
        row = conn.execute(
            "SELECT id, user_id, ticker, added_at FROM watchlist WHERE id = ?", (new_id,)
        ).fetchone()
        return _row_to_watchlist_item(row)


def _remove_from_watchlist_sync(ticker: str, user_id: str, db_path: Path | None) -> bool:
    normalized = _normalize_ticker(ticker)
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, normalized)
        )
        return cur.rowcount > 0


def _get_positions_sync(user_id: str, db_path: Path | None) -> list[Position]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id, user_id, ticker, quantity, avg_cost, updated_at FROM positions "
            "WHERE user_id = ? ORDER BY ticker ASC",
            (user_id,),
        ).fetchall()
        return [_row_to_position(r) for r in rows]


def _get_position_sync(ticker: str, user_id: str, db_path: Path | None) -> Position | None:
    normalized = _normalize_ticker(ticker)
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT id, user_id, ticker, quantity, avg_cost, updated_at FROM positions "
            "WHERE user_id = ? AND ticker = ?",
            (user_id, normalized),
        ).fetchone()
        return _row_to_position(row) if row is not None else None


def _validate_trade_inputs(side: str, quantity: float, price: float) -> None:
    if side not in ("buy", "sell"):
        raise InvalidTradeError(f"side must be 'buy' or 'sell', got {side!r}")
    if not math.isfinite(quantity) or quantity <= 0:
        raise InvalidTradeError(f"quantity must be a positive finite number, got {quantity!r}")
    if not math.isfinite(price) or price <= 0:
        raise InvalidTradeError(f"price must be a positive finite number, got {price!r}")


def _execute_trade_sync(
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str,
    db_path: Path | None,
) -> TradeResult:
    _validate_trade_inputs(side, quantity, price)
    normalized = _normalize_ticker(ticker)
    notional = round(quantity * price, 2)

    with get_connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            profile_row = conn.execute(
                "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
            ).fetchone()
            cash_balance = profile_row["cash_balance"]

            position_row = conn.execute(
                "SELECT id, quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, normalized),
            ).fetchone()
            held_quantity = position_row["quantity"] if position_row is not None else 0.0
            held_avg_cost = position_row["avg_cost"] if position_row is not None else 0.0

            if side == "buy":
                if notional > cash_balance:
                    raise InsufficientCashError(required=notional, available=cash_balance)
                new_cash = round(cash_balance - notional, 2)
                new_quantity = held_quantity + quantity
                # avg_cost moves on buys only (weighted average of old + new lot)
                new_avg_cost = ((held_quantity * held_avg_cost) + (quantity * price)) / new_quantity
            else:  # sell
                if quantity > held_quantity + _SHARES_EPSILON:
                    raise InsufficientSharesError(requested=quantity, held=held_quantity)
                new_cash = round(cash_balance + notional, 2)
                new_quantity = held_quantity - quantity
                new_avg_cost = held_avg_cost  # sells never change avg_cost

            conn.execute(
                "UPDATE users_profile SET cash_balance = ? WHERE id = ?", (new_cash, user_id)
            )

            updated_at = _now()
            if abs(new_quantity) < _POSITION_EPSILON:
                # Delete float-residual/closed positions rather than store noise.
                conn.execute(
                    "DELETE FROM positions WHERE user_id = ? AND ticker = ?", (user_id, normalized)
                )
                result_position: Position | None = None
            elif position_row is not None:
                conn.execute(
                    "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? "
                    "WHERE user_id = ? AND ticker = ?",
                    (new_quantity, new_avg_cost, updated_at, user_id, normalized),
                )
                result_position = Position(
                    id=position_row["id"],
                    user_id=user_id,
                    ticker=normalized,
                    quantity=new_quantity,
                    avg_cost=new_avg_cost,
                    updated_at=updated_at,
                )
            else:
                new_position_id = str(uuid4())
                conn.execute(
                    "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (new_position_id, user_id, normalized, new_quantity, new_avg_cost, updated_at),
                )
                result_position = Position(
                    id=new_position_id,
                    user_id=user_id,
                    ticker=normalized,
                    quantity=new_quantity,
                    avg_cost=new_avg_cost,
                    updated_at=updated_at,
                )

            trade_id = str(uuid4())
            executed_at = _now()
            conn.execute(
                "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (trade_id, user_id, normalized, side, quantity, price, executed_at),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    trade = Trade(
        id=trade_id,
        user_id=user_id,
        ticker=normalized,
        side=side,
        quantity=quantity,
        price=price,
        executed_at=executed_at,
    )
    return TradeResult(trade=trade, position=result_position, cash_balance=new_cash)


def _get_trades_sync(user_id: str, limit: int, db_path: Path | None) -> list[Trade]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id, user_id, ticker, side, quantity, price, executed_at FROM trades "
            "WHERE user_id = ? ORDER BY executed_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [_row_to_trade(r) for r in rows]


def _record_snapshot_sync(
    total_value: float, user_id: str, db_path: Path | None
) -> PortfolioSnapshot:
    snapshot_id = str(uuid4())
    recorded_at = _now()
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (snapshot_id, user_id, total_value, recorded_at),
        )
    return PortfolioSnapshot(
        id=snapshot_id, user_id=user_id, total_value=total_value, recorded_at=recorded_at
    )


def _get_snapshots_sync(
    user_id: str, since: str | None, limit: int, db_path: Path | None
) -> list[PortfolioSnapshot]:
    with get_connection(db_path) as conn:
        if since is not None:
            rows = conn.execute(
                "SELECT id, user_id, total_value, recorded_at FROM portfolio_snapshots "
                "WHERE user_id = ? AND recorded_at >= ? ORDER BY recorded_at ASC LIMIT ?",
                (user_id, since, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, user_id, total_value, recorded_at FROM portfolio_snapshots "
                "WHERE user_id = ? ORDER BY recorded_at ASC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [_row_to_snapshot(r) for r in rows]


def _add_chat_message_sync(
    role: str, content: str, actions: str | None, user_id: str, db_path: Path | None
) -> ChatMessage:
    if role not in ("user", "assistant"):
        raise InvalidTradeError(f"role must be 'user' or 'assistant', got {role!r}")
    message_id = str(uuid4())
    created_at = _now()
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (message_id, user_id, role, content, actions, created_at),
        )
    return ChatMessage(
        id=message_id,
        user_id=user_id,
        role=role,
        content=content,
        actions=actions,
        created_at=created_at,
    )


def _get_chat_history_sync(user_id: str, limit: int, db_path: Path | None) -> list[ChatMessage]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id, user_id, role, content, actions, created_at FROM chat_messages "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [_row_to_chat_message(r) for r in reversed(rows)]


def _reset_portfolio_sync(user_id: str, db_path: Path | None) -> None:
    from .seed import DEFAULT_CASH_BALANCE

    now = _now()
    with get_connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
                (DEFAULT_CASH_BALANCE, user_id),
            )
            conn.execute("DELETE FROM positions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM trades WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM portfolio_snapshots WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM watchlist WHERE user_id = ?", (user_id,))
            for ticker in DEFAULT_WATCHLIST:
                conn.execute(
                    "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                    (str(uuid4()), user_id, ticker, now),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


# --------------------------------------------------------------------------
# Public async API
# --------------------------------------------------------------------------


async def init_db() -> None:
    """Force schema creation + seeding now. Optional — every function below
    triggers the same lazy init on its own first call."""
    await asyncio.to_thread(_init_db_sync, None)


async def get_user_profile(user_id: str = DEFAULT_USER_ID) -> UserProfile:
    """Fetch the user's profile row. Always exists after lazy init."""
    return await asyncio.to_thread(_get_user_profile_sync, user_id, None)


async def get_cash_balance(user_id: str = DEFAULT_USER_ID) -> float:
    """Convenience: just the cash_balance float."""
    return await asyncio.to_thread(_get_cash_balance_sync, user_id, None)


async def get_watchlist(user_id: str = DEFAULT_USER_ID) -> list[WatchlistItem]:
    """All watchlist rows for the user, ordered by added_at ascending."""
    return await asyncio.to_thread(_get_watchlist_sync, user_id, None)


async def add_to_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> WatchlistItem:
    """Add a ticker (normalized: stripped, upper-cased). Idempotent: if
    (user_id, ticker) already exists, returns the existing row unchanged."""
    return await asyncio.to_thread(_add_to_watchlist_sync, ticker, user_id, None)


async def remove_from_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """Remove a ticker (normalized the same way). Returns True if a row was
    deleted, False if it wasn't present."""
    return await asyncio.to_thread(_remove_from_watchlist_sync, ticker, user_id, None)


async def get_positions(user_id: str = DEFAULT_USER_ID) -> list[Position]:
    """All open positions for the user, ordered by ticker ascending."""
    return await asyncio.to_thread(_get_positions_sync, user_id, None)


async def get_position(ticker: str, user_id: str = DEFAULT_USER_ID) -> Position | None:
    """Single position by ticker (normalized), or None if not held."""
    return await asyncio.to_thread(_get_position_sync, ticker, user_id, None)


async def execute_trade(
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = DEFAULT_USER_ID,
) -> TradeResult:
    """Execute a market order inside a single BEGIN IMMEDIATE transaction.

    Raises InvalidTradeError / InsufficientCashError / InsufficientSharesError
    on validation failure; writes nothing in that case.
    """
    return await asyncio.to_thread(_execute_trade_sync, ticker, side, quantity, price, user_id, None)


async def get_trades(user_id: str = DEFAULT_USER_ID, limit: int = 100) -> list[Trade]:
    """Trade history, most recent first."""
    return await asyncio.to_thread(_get_trades_sync, user_id, limit, None)


async def record_snapshot(total_value: float, user_id: str = DEFAULT_USER_ID) -> PortfolioSnapshot:
    """Insert a portfolio_snapshots row with the caller-computed total_value."""
    return await asyncio.to_thread(_record_snapshot_sync, total_value, user_id, None)


async def get_snapshots(
    user_id: str = DEFAULT_USER_ID,
    since: str | None = None,
    limit: int = 500,
) -> list[PortfolioSnapshot]:
    """Snapshots ordered oldest-first (chronological, ready for a line chart)."""
    return await asyncio.to_thread(_get_snapshots_sync, user_id, since, limit, None)


async def add_chat_message(
    role: str,
    content: str,
    actions: str | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> ChatMessage:
    """Append a chat message. `actions` is stored verbatim (already-JSON text)."""
    return await asyncio.to_thread(_add_chat_message_sync, role, content, actions, user_id, None)


async def get_chat_history(user_id: str = DEFAULT_USER_ID, limit: int = 20) -> list[ChatMessage]:
    """Most recent `limit` messages, returned oldest-first."""
    return await asyncio.to_thread(_get_chat_history_sync, user_id, limit, None)


async def reset_portfolio(user_id: str = DEFAULT_USER_ID) -> None:
    """Restore the user to a fresh-install state (cash, positions, trades,
    snapshots, chat history, and watchlist all reset to defaults)."""
    await asyncio.to_thread(_reset_portfolio_sync, user_id, None)
