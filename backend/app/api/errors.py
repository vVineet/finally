"""Uniform error handling (PLAN §13.C5) and ticker validation (§13.B3).

C5: every 4xx/5xx uses FastAPI's `{"detail": "..."}` shape. This module is
the one place that's enforced:

- `register_exception_handlers` maps `app.db` errors (`InvalidTradeError`,
  `InsufficientCashError`, `InsufficientSharesError`) to 400s, reshapes
  pydantic's `RequestValidationError` (whose default `detail` is a list of
  error objects) down to a single string, and leaves the SPA-fallback /
  plain 404-JSON behavior to `app.main`'s handler for
  `starlette.exceptions.HTTPException`.
- `normalize_ticker` is the one ticker format gate (strip, uppercase,
  charset/length check) shared by every endpoint that accepts a ticker
  from the request body/path, so the rule is defined once.
"""

from __future__ import annotations

import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.db import DBError, InsufficientCashError, InsufficientSharesError, InvalidTradeError

# 1-10 chars, starts with a letter, remainder alnum/dot/hyphen (covers
# tickers like "V", "AAPL", "BRK.B"). Deliberately permissive rather than an
# allowlist -- PLAN §13.B3 leaves real-symbol validation out of scope; this
# is a format sanity check, not a "does this ticker exist" check.
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def normalize_ticker(raw: str) -> str:
    """Strip + uppercase a ticker and validate its format.

    Raises HTTPException(400, {"detail": ...}) if the result doesn't look
    like a ticker symbol at all (empty, too long, bad characters).
    """
    ticker = raw.strip().upper()
    if not TICKER_RE.match(ticker):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ticker format: {raw!r}",
        )
    return ticker


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InsufficientCashError)
    async def _insufficient_cash(request: Request, exc: InsufficientCashError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(InsufficientSharesError)
    async def _insufficient_shares(request: Request, exc: InsufficientSharesError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(InvalidTradeError)
    async def _invalid_trade(request: Request, exc: InvalidTradeError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(DBError)
    async def _db_error(request: Request, exc: DBError) -> JSONResponse:
        # Catch-all for any other app.db error we haven't special-cased above.
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
            message = first.get("msg", "Invalid request")
            detail = f"{loc}: {message}" if loc else message
        else:
            detail = "Invalid request"
        return JSONResponse(status_code=422, content={"detail": detail})
