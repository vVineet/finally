"""Default seed data, applied idempotently on every schema init."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

DEFAULT_USER_ID = "default"
DEFAULT_CASH_BALANCE = 10000.0
DEFAULT_WATCHLIST: tuple[str, ...] = (
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
)


def seed_defaults(conn: sqlite3.Connection) -> None:
    """Insert the default profile and watchlist if not already present.

    Uses INSERT OR IGNORE keyed on each table's unique constraint
    (users_profile.id, watchlist(user_id, ticker)), so calling this
    against an already-seeded database is a cheap no-op.
    """
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, now),
    )
    for ticker in DEFAULT_WATCHLIST:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid4()), DEFAULT_USER_ID, ticker, now),
        )
