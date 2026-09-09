"""FastAPI app assembly (PLAN §8, §11, §13.D).

Route mount order matters here (§13.D's "classic failure"): every `/api/*`
router is included first, so exact routes always win the match before the
catch-all static mount ever sees the request. The static mount (serving the
built frontend) is added last, and only if the directory actually exists --
`frontend/` doesn't exist yet in this stage, so the app must boot cleanly
without it (degrading to a plain JSON 404 for any non-/api path).

A single exception handler for Starlette's HTTPException does double duty:
- for `/api/*` paths, it guarantees the uniform `{"detail": "..."}` shape
  (§13.C5) even for 404s the static mount itself might raise;
- for any other path, a 404 is treated as an SPA route and serves
  `index.html` if it exists, so client-side routing works without every
  possible frontend path needing its own StaticFiles entry.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from app.api import chat, health, history, portfolio, register_exception_handlers, trades, watchlist
from app.db import init_db
from app.market import PriceCache, create_market_data_source, create_stream_router
from app.portfolio import get_tracked_tickers, snapshot_loop

logger = logging.getLogger(__name__)

# backend/app/main.py -> backend/app -> backend -> backend/static (default)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _static_dir() -> Path:
    configured = os.environ.get("STATIC_DIR", "").strip()
    if configured:
        return Path(configured)
    return _BACKEND_ROOT / "static"


_UNSET = object()


def create_app(static_dir: Path | None | object = _UNSET) -> FastAPI:
    """Build the FastAPI app.

    `static_dir`: defaults to the `STATIC_DIR` env var (or `backend/static`)
    when omitted entirely. Pass `None` explicitly to disable static/SPA
    serving outright (used by tests), or a `Path` to point at a specific
    directory (also used by tests, to exercise the SPA-fallback behavior
    without needing a real frontend build).
    """
    resolved_static_dir = _static_dir() if static_dir is _UNSET else static_dir

    # Created once per app instance (not inside lifespan) so the SSE stream
    # router below and the lifespan's market data source share the exact
    # same PriceCache -- otherwise the router would read from a cache the
    # background source never writes to.
    price_cache = PriceCache()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await init_db()

        market_source = create_market_data_source(price_cache)
        app.state.market_source = market_source

        tickers = sorted(await get_tracked_tickers())
        await market_source.start(tickers)

        snapshot_task = asyncio.create_task(snapshot_loop(price_cache))
        app.state.snapshot_task = snapshot_task

        try:
            yield
        finally:
            snapshot_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await snapshot_task
            await market_source.stop()

    app = FastAPI(title="FinAlly API", lifespan=lifespan)
    # Available immediately (even before/without lifespan running, e.g. in
    # tests that hit routes directly without a `with TestClient(app)` block).
    app.state.price_cache = price_cache
    app.state.market_source = None

    # --- /api/* routers first: these must never be shadowed by the static
    # mount below. ---
    app.include_router(health.router)
    app.include_router(portfolio.router)
    app.include_router(watchlist.router)
    app.include_router(trades.router)
    app.include_router(chat.router)
    app.include_router(history.router)
    app.include_router(create_stream_router(price_cache))

    register_exception_handlers(app)

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(request, exc: StarletteHTTPException):
        path = request.url.path
        if exc.status_code == 404 and not path.startswith("/api") and resolved_static_dir is not None:
            index_file = resolved_static_dir / "index.html"
            if index_file.is_file():
                return FileResponse(index_file)
        detail = exc.detail if exc.detail is not None else "Error"
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    # --- Static mount last: only intercepts paths no /api router matched.
    # Absent/missing directory degrades gracefully (no frontend build yet in
    # this stage) rather than crashing StaticFiles' check_dir=True. ---
    if resolved_static_dir is not None and resolved_static_dir.is_dir():
        # NOT html=True: in that mode Starlette *returns* 404.html on a miss
        # instead of *raising* HTTPException, so _http_exception_handler below
        # never runs -- breaking both the /api JSON 404 shape (C5) and the SPA
        # fallback. Next's static export always emits a 404.html, so this is
        # not hypothetical. The handler serves index.html for "/" and deep
        # links on its own.
        app.mount("/", StaticFiles(directory=resolved_static_dir), name="static")
    else:
        logger.warning(
            "Static directory %s not found; frontend will not be served "
            "(expected before the frontend build exists / outside Docker).",
            resolved_static_dir,
        )

    return app


app = create_app()
