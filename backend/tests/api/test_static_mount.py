"""Static/SPA mount ordering (PLAN §13.D): unknown non-/api routes serve
index.html, unknown /api/* routes 404 as JSON, and real /api routes are
never shadowed by the catch-all static mount. Also covers graceful
degradation when the static directory doesn't exist (this stage, before
frontend/ is built).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    return path


@pytest.fixture
def static_dir(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html><body>FinAlly SPA</body></html>")
    (static / "favicon.ico").write_bytes(b"\x00")
    return static


def test_unknown_api_route_is_json_404(db_path, static_dir):
    app = create_app(static_dir=static_dir)
    client = TestClient(app)

    response = client.get("/api/this-route-does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
    assert response.headers["content-type"].startswith("application/json")


def test_real_api_route_is_not_shadowed_by_static_mount(db_path, static_dir):
    app = create_app(static_dir=static_dir)
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_non_api_route_serves_index_html(db_path, static_dir):
    app = create_app(static_dir=static_dir)
    client = TestClient(app)

    response = client.get("/some/client/side/route")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "FinAlly SPA" in response.text


def test_existing_static_asset_is_served_directly(db_path, static_dir):
    app = create_app(static_dir=static_dir)
    client = TestClient(app)

    response = client.get("/favicon.ico")

    assert response.status_code == 200


def test_root_serves_index_html(db_path, static_dir):
    app = create_app(static_dir=static_dir)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "FinAlly SPA" in response.text


def test_missing_static_dir_degrades_gracefully_not_a_crash(db_path, tmp_path):
    missing = tmp_path / "does-not-exist"

    app = create_app(static_dir=missing)  # must not raise
    client = TestClient(app)

    # api still works
    assert client.get("/api/health").status_code == 200
    # unmatched api route -> json 404
    api_404 = client.get("/api/nope")
    assert api_404.status_code == 404
    assert api_404.json() == {"detail": "Not Found"}
    # unmatched non-api route -> plain json 404 (no frontend to fall back to)
    other_404 = client.get("/anything")
    assert other_404.status_code == 404
    assert other_404.json() == {"detail": "Not Found"}


def test_lifespan_starts_and_stops_market_source_and_snapshot_task(db_path, monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    app = create_app(static_dir=None)

    with TestClient(app) as client:
        response = client.get("/api/watchlist")
        assert response.status_code == 200
        assert app.state.market_source is not None
        assert app.state.market_source.get_tickers()  # started with the default watchlist
        assert not app.state.snapshot_task.done()

    # After exiting the context, lifespan shutdown has run.
    assert app.state.snapshot_task.cancelled() or app.state.snapshot_task.done()
