"""Tests for lazy schema initialization and seeding (schema.py, seed.py,
connection.py)."""

from __future__ import annotations

import sqlite3

from app.db.connection import get_connection
from app.db.seed import DEFAULT_CASH_BALANCE, DEFAULT_WATCHLIST


class TestFreshDatabase:
    """Seeding behavior against a database file that doesn't exist yet."""

    def test_file_created_on_first_connection(self, db_path):
        assert not db_path.exists()
        with get_connection():
            pass
        assert db_path.exists()

    def test_all_six_tables_created(self, db_path):
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            table_names = {r["name"] for r in rows}
        expected = {
            "users_profile",
            "watchlist",
            "positions",
            "trades",
            "portfolio_snapshots",
            "chat_messages",
        }
        assert expected.issubset(table_names)

    def test_default_profile_seeded(self, db_path):
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM users_profile WHERE id = 'default'").fetchone()
        assert row is not None
        assert row["cash_balance"] == DEFAULT_CASH_BALANCE
        assert row["created_at"]  # non-empty ISO timestamp

    def test_default_watchlist_seeded(self, db_path):
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT ticker FROM watchlist WHERE user_id = 'default' ORDER BY ticker"
            ).fetchall()
        tickers = {r["ticker"] for r in rows}
        assert tickers == set(DEFAULT_WATCHLIST)
        assert len(rows) == 10

    def test_other_tables_start_empty(self, db_path):
        with get_connection() as conn:
            for table in ("positions", "trades", "portfolio_snapshots", "chat_messages"):
                count = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
                assert count == 0, f"{table} should start empty"


class TestIdempotentReinit:
    """Re-opening a connection against an already-initialized database must
    not duplicate seed data or fail."""

    def test_reopening_does_not_duplicate_profile(self, db_path):
        with get_connection():
            pass
        with get_connection():
            pass
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM users_profile").fetchone()["c"]
        assert count == 1

    def test_reopening_does_not_duplicate_watchlist(self, db_path):
        for _ in range(3):
            with get_connection():
                pass
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM watchlist").fetchone()["c"]
        assert count == 10

    def test_reinit_preserves_user_modifications(self, db_path):
        """Re-running init must not clobber data the user has since changed."""
        with get_connection() as conn:
            conn.execute("UPDATE users_profile SET cash_balance = 5000.0 WHERE id = 'default'")
        with get_connection() as conn:
            row = conn.execute("SELECT cash_balance FROM users_profile WHERE id = 'default'").fetchone()
        assert row["cash_balance"] == 5000.0

    def test_create_table_if_not_exists_is_safe_to_rerun(self, db_path):
        """Directly re-running the schema script against a populated DB
        must not raise (guards against a future accidental DROP/CREATE)."""
        from app.db.schema import SCHEMA_SQL

        with get_connection() as conn:
            conn.executescript(SCHEMA_SQL)  # should not raise
            count = conn.execute("SELECT COUNT(*) AS c FROM users_profile").fetchone()["c"]
        assert count == 1

    def test_removed_default_ticker_is_not_resurrected(self, db_path):
        """Regression test: deleting a default watchlist ticker and then
        opening a fresh connection (which re-runs the idempotent init path)
        must not bring it back. INSERT OR IGNORE alone would not catch this
        because a deleted row leaves no unique-constraint conflict."""
        with get_connection() as conn:
            conn.execute("DELETE FROM watchlist WHERE user_id = 'default' AND ticker = 'AAPL'")
        with get_connection() as conn:
            pass  # re-triggers the lazy-init path
        with get_connection() as conn:
            tickers = {
                r["ticker"]
                for r in conn.execute(
                    "SELECT ticker FROM watchlist WHERE user_id = 'default'"
                ).fetchall()
            }
        assert "AAPL" not in tickers
        assert len(tickers) == 9

    def test_journal_mode_is_wal(self, db_path):
        with get_connection() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"

    def test_connection_is_check_same_thread_false(self, db_path):
        # A connection created with check_same_thread=False can be used from
        # a different thread than the one that created it, without raising
        # sqlite3.ProgrammingError.
        import threading

        errors = []

        def use_from_other_thread(conn):
            try:
                conn.execute("SELECT 1").fetchone()
            except sqlite3.ProgrammingError as exc:  # pragma: no cover - failure path
                errors.append(exc)

        with get_connection() as conn:
            t = threading.Thread(target=use_from_other_thread, args=(conn,))
            t.start()
            t.join()
        assert not errors
