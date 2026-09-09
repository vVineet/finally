"""SQLite connection management with lazy schema initialization.

See planning/DATABASE_DESIGN.md §3-4 for the rationale behind these choices:
WAL mode, one connection per call (no shared pool), `isolation_level=None`
so callers control transactions explicitly (required for BEGIN IMMEDIATE),
and re-running the idempotent CREATE-TABLE-IF-NOT-EXISTS / INSERT-OR-IGNORE
init on every connection open rather than caching an "already initialized"
flag (which would misbehave across DATABASE_PATH changes, e.g. in tests).
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .schema import SCHEMA_SQL
from .seed import seed_defaults

DEFAULT_USER_ID = "default"

# app/db/connection.py -> app/db -> app -> backend -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]


def get_db_path() -> Path:
    """Resolve the SQLite database file path.

    Reads the DATABASE_PATH env var fresh on every call (not cached at
    import time, so tests can monkeypatch it per-test). Falls back to
    "db/finally.db" relative to the repo root — the container overrides
    this to "/app/db/finally.db" via the environment.
    """
    configured = os.environ.get("DATABASE_PATH", "").strip()
    if configured:
        return Path(configured)
    return _REPO_ROOT / "db" / "finally.db"


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a single-use connection with the pragmas this project relies on."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30.0)
    conn.isolation_level = None  # autocommit; we manage transactions explicitly
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _ensure_initialized(conn: sqlite3.Connection) -> None:
    """Create schema (if absent) and seed defaults (if the DB is empty).

    Seeding is gated on `users_profile` having zero rows, not run
    unconditionally: once the default profile row exists, the database is
    considered "already seeded" and we must not re-insert default watchlist
    tickers a user has since removed. (INSERT OR IGNORE alone is not
    sufficient here — once a row is deleted, there is no longer a unique
    constraint conflict to IGNORE, so an unconditional re-seed would
    silently resurrect it on the next connection.)
    """
    conn.executescript(SCHEMA_SQL)
    row = conn.execute("SELECT COUNT(*) AS c FROM users_profile").fetchone()
    if row["c"] == 0:
        seed_defaults(conn)


@contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open a connection for a single unit of work.

    Ensures schema/seed data exist, yields the connection, and always
    closes it on exit. Because `isolation_level=None`, no implicit
    transaction is open on entry or exit — multi-statement callers (e.g.
    execute_trade) issue their own BEGIN IMMEDIATE / COMMIT / ROLLBACK.
    """
    path = db_path if db_path is not None else get_db_path()
    conn = _connect(path)
    try:
        _ensure_initialized(conn)
        yield conn
    finally:
        conn.close()
