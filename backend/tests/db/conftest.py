"""Fixtures for database layer tests.

Each test gets its own SQLite file under pytest's tmp_path, pointed to via
the DATABASE_PATH env var (read fresh by app.db.connection.get_db_path() on
every call — no caching to worry about).
"""

from __future__ import annotations

import pytest


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """A fresh, unseeded SQLite file path for this test, wired via env var."""
    path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    return path
