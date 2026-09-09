# FinAlly — Backend API Summary

Status: **done** (except `POST /api/chat`'s handler body, explicitly left
to the LLM Engineer — the route, request validation, and full target
contract are in place). Implements PLAN.md §8 (API Endpoints) plus the
§13.B1 additions (`GET /api/chat/history`, `GET /api/trades`, `POST
/api/portfolio/reset`), two follow-up additions after coordinator
course-corrections — §13.B13/C4 (`GET /api/history/{ticker}`) and §13.A1
(`day_change`/`day_change_percent` on the SSE stream) — and the binding
review decisions A4, A6, B2, B4, B6, C2, C3, C5, and §13.D.

Full request/response contract lives in `planning/API_CONTRACT.md` —
that's the document the Frontend and LLM engineers should code against.
This file covers what was built, how, and the real test results.

## What was built

```
backend/app/portfolio/
    __init__.py     Public API surface
    valuation.py    compute_total_value() (B6, defined once), PositionView
                    + build_position_view() for per-position P&L
    tracking.py     get_tracked_tickers() (A4: watchlist ∪ non-zero
                    positions), sync_tracked_tickers() reconciling a
                    MarketDataSource against it
    snapshotter.py  snapshot_once() (shared by the trade/reset endpoints
                    and the background loop), snapshot_loop() (30s cadence)

backend/app/api/
    __init__.py     Router aggregation + register_exception_handlers
    deps.py         get_price_cache/get_market_source (pull from
                    request.app.state; overridable in tests)
    schemas.py      Pydantic request bodies (TradeRequest,
                    WatchlistAddRequest, ChatRequest)
    errors.py       normalize_ticker() (the one ticker-format gate, B3),
                    exception handlers mapping app.db errors -> 400
                    {"detail": str(exc)} and reshaping pydantic's
                    RequestValidationError to a single string (C5)
    health.py       GET /api/health
    portfolio.py    GET/POST /api/portfolio, /trade, /history, /reset
    watchlist.py    GET/POST /api/watchlist, DELETE /api/watchlist/{ticker}
    trades.py       GET /api/trades
    chat.py         GET /api/chat/history (implemented), POST /api/chat
                    (stub, 501, contract documented)
    history.py      GET /api/history/{ticker} (§13.B13/C4, added in a
                    follow-up pass -- see below)

backend/app/main.py
    create_app(static_dir=...) factory + module-level `app`. Lifespan:
    init_db() -> create_market_data_source() -> start() with A4's tracked-
    ticker set -> asyncio.create_task(snapshot_loop) ; reverse on
    shutdown. /api/* routers included before the static mount; a single
    StarletteHTTPException handler gives uniform {"detail": ...} JSON for
    /api/* 404s and serves index.html for any other unmatched path when a
    static build exists, degrading to plain JSON 404s when it doesn't
    (frontend/ doesn't exist yet in this stage -- verified not to crash).

backend/tests/portfolio/   13 tests (valuation, tracking, snapshotter)
backend/tests/api/         43 tests (health, watchlist, portfolio, trades,
                            chat, static mount ordering, history)
backend/tests/market/      3 new files, added alongside the pre-existing
                            test_cache.py/test_models.py rather than
                            editing them:
                              test_cache_history.py       7 tests
                              test_cache_day_change.py    7 tests
                              test_models_day_change.py   6 tests
```

Two small, backward-compatible additions to the market data component
(coordinated, not a rewrite -- see the binding-decision entries below for
exactly what changed and why neither breaks the existing 73-test suite):
- `app/market/cache.py`: the `HISTORY_MAXLEN`-deep ring buffer (`GET
  /api/history/{ticker}`) and per-ticker `open_price` tracking
  (`day_change`/`day_change_percent`).
- `app/market/models.py`: `PriceUpdate` gained an optional `open_price`
  field (default `None`) and the `day_change`/`day_change_percent`
  properties, included in `to_dict()`. `app/market/stream.py` was **not**
  touched -- it already serializes whatever `to_dict()` returns.

## Binding decisions — how each was implemented

- **A4**: `get_tracked_tickers()` = watchlist ∪ tickers with
  `abs(quantity) > 1e-9`. `sync_tracked_tickers()` diffs that set against
  `source.get_tickers()` and calls `add_ticker`/`remove_ticker` for the
  difference. Called after every watchlist add/remove, every trade, and
  reset; called once at startup via `source.start(sorted(tickers))`. Test:
  `tests/portfolio/test_tracking.py::test_sync_tracked_tickers_never_drops_a_held_ticker`
  and `tests/api/test_watchlist.py::test_remove_ticker_still_held_keeps_pricing_it`.
- **B6**: `app.portfolio.compute_total_value(cash_balance, positions,
  price_cache)` is the only place `total_value` is computed; every
  endpoint (`GET /api/portfolio`, the trade/reset responses, and
  `snapshot_once`) calls it. Positions with no cached price are excluded
  from the sum, never valued at 0/avg_cost.
- **B2**: `GET /api/portfolio/history` takes `since` (ISO 8601, 400 if
  unparseable) and `limit` (`1..2000`, default 200, 422 outside range via
  FastAPI `Query(ge=..., le=...)`).
- **B4**: `POST /api/portfolio/trade` rejects `quantity <= 0` or
  non-finite (checked with `math.isfinite`) before touching the DB;
  rejects when `price_cache.get_price(ticker)` is `None` rather than
  passing `0`/`None` into `execute_trade`; on success, auto-adds the
  ticker to the watchlist if it wasn't there.
- **C2**: `POST /api/portfolio/trade` returns `{"trade": ..., "portfolio":
  ...}`; `POST /api/portfolio/reset` returns `{"portfolio": ...,
  "watchlist": ...}`; `POST`/`DELETE /api/watchlist*` return the updated
  `{"watchlist": [...]}`. No endpoint requires a follow-up GET.
- **C3**: `GET /api/watchlist` (and the `watchlist` array embedded in
  reset's response) contains only `{"ticker", "added_at"}` — no price
  field exists on that object anywhere in the codebase.
- **C5**: `register_exception_handlers` maps `InvalidTradeError` /
  `InsufficientCashError` / `InsufficientSharesError` / the `DBError` base
  to `400 {"detail": str(exc)}`, and reshapes
  `RequestValidationError.errors()` down to a single `"field: message"`
  string at `422`. The `StarletteHTTPException` handler in `main.py`
  covers everything else (404s, the 501 chat stub, the 404 watchlist
  removal) with the same `{"detail": ...}` shape.
- **A6**: every timestamp built in `app/api`/`app/portfolio` uses
  `datetime.now(UTC).isoformat()`; `app.db`'s own timestamps are already
  ISO strings. Nothing in this layer touches `PriceUpdate.timestamp`
  (epoch float) except reading `.price` off it — that field never leaks
  into a REST response body.
- **§13.D**: verified explicitly in
  `tests/api/test_static_mount.py` — real `/api/*` routes are never
  shadowed by the catch-all static `Mount("/")` (registered last); an
  unmatched `/api/*` path 404s as JSON; an unmatched non-`/api` path
  serves `index.html` when a static build exists; a missing static
  directory (this stage's actual state — `frontend/` doesn't exist)
  degrades to plain JSON 404s everywhere without crashing `create_app()`.
- **§13.B13/C4** (added in a follow-up pass, after the coordinator flagged
  it was missing from the original brief): `PriceCache` in
  `app/market/cache.py` now keeps a `collections.deque(maxlen=600)` per
  ticker, appended to inside the same lock `update()` already takes (O(1)
  append, deque's own `maxlen` eviction — no extra bookkeeping, no
  meaningful hot-path cost) and evicted in `remove()`. `GET
  /api/history/{ticker}` reads it via the new `PriceCache.get_history()`
  and returns `{"ticker", "points": [{"t", "price"}, ...]}` oldest-first,
  `200` with `"points": []` for an unknown/never-ticked ticker (not a
  404 — a just-added ticker legitimately has no history yet). `t` is the
  one deliberate exception to A6's `"+00:00"` convention: ISO 8601 UTC
  with millisecond precision and a literal `"Z"` suffix, to match the
  exact contract specified by the coordinator (the Frontend Engineer was
  already coding against it). `limit` defaults to and caps at 600 (422
  outside `1..600`).
- **§13.A1** (second follow-up, same batch): `PriceCache` now also tracks
  an `open_price` per ticker (a separate dict, populated on that ticker's
  first `update()` since construction or since its last `remove()`, never
  overwritten after). `PriceUpdate` exposes `day_change`/
  `day_change_percent` computed against it, using the exact field names
  the Frontend Engineer specified and is already coding against. Both are
  `0.0` (never a `ZeroDivisionError`/`NaN`) when there's no open price yet
  or it's `0` — same defensive pattern as the existing `change_percent`.
  Documented explicitly in `planning/API_CONTRACT.md` that "day" here
  means "since this process started tracking the ticker," not a true
  market previous-close (the simulator has no such concept, and even
  under `MASSIVE_API_KEY` it's "price at first poll this process made,"
  not the exchange's actual prior close) — so the UI should label it
  something like "since session start," not "1D %".

## A design note beyond the binding decisions

`create_app()` builds the single shared `PriceCache` *before* defining the
`lifespan` closure, and passes that same instance both to
`create_stream_router()` (included as a normal router) and into the
lifespan's `create_market_data_source()` call. Building it inside
`lifespan` instead would have given the SSE router and the background
market data source two different caches — the classic bug where the
stream never shows a price because nothing writes to the cache it reads
from. Worth flagging since it's an easy mistake to reintroduce if
`main.py` is refactored later.

## What the LLM Engineer must know (also in API_CONTRACT.md)

- `POST /api/chat` currently always returns `501`. The request body
  (`{"message": str}`) is already validated.
- The target response shape separates the LLM's prose (`message`) from
  structured execution results (`trades_executed`, `trades_failed`,
  `watchlist_changes`) per PLAN §13.A3 — the LLM cannot know a trade's
  outcome before writing `message`, so the system prompt must avoid
  claiming completion ("I'll buy..." not "I bought...").
- Reuse `app.portfolio.sync_tracked_tickers`, `app.portfolio.snapshot_once`,
  and `app.db.execute_trade`/`add_to_watchlist`/`remove_from_watchlist`
  directly for any trades/watchlist changes the LLM decides to execute —
  don't reimplement validation. `app.api.errors.normalize_ticker` is the
  ticker-format gate to reuse too.
- Persist messages via `app.db.add_chat_message(role, content, actions=
  json.dumps(...) or None)`.

## What the Frontend Engineer must know (also in API_CONTRACT.md)

- One error shape everywhere: `response.json().detail` is always a
  string.
- `GET /api/watchlist` has no prices — get them from `/api/stream/prices`
  (already built, see `planning/MARKET_DATA_SUMMARY.md`).
- After a trade/watchlist mutation, use the response body directly; don't
  re-fetch.
- `total_value`/`market_value`/`unrealized_pnl` fields can be `null` for a
  position whose ticker hasn't ticked yet (e.g. seconds after adding it) —
  render that as "—" or similar, not `$0.00`.
- The static file mount expects the built frontend at `backend/static/`
  by default (overridable via the `STATIC_DIR` env var) — see
  `app/main.py`. That directory doesn't need to exist for the backend to
  run; it's created by the Docker build stage described in PLAN §11.

## Test results (real output)

```
$ uv run --extra dev pytest -q
208 passed in 5.36s
```
(132 pre-existing in `tests/db` + `tests/market` — all still passing, no
regressions to the market data suite; 76 new: 13 in `tests/portfolio`, 43
in `tests/api`, 20 in `tests/market` across the three new files listed
above.)

```
$ uv run --extra dev ruff check app/ tests/
All checks passed!
```

Coverage of the original stage-2 code (`pytest tests/api tests/portfolio
--cov=app.api --cov=app.portfolio --cov=app.main --cov-report=term-missing`):
**97%** (302/312 statements). The gaps are two `Depends`-injector function
bodies that are always replaced via `dependency_overrides` in tests except
the one real-lifespan test (which doesn't happen to call them), the
`STATIC_DIR` env-var branch in `main.py` (trivial), and 4 lines in the
background snapshot loop's exception-logging branch (would need to inject
a DB failure mid-loop to exercise, not worth the complexity for a
defensive path — same call made in `planning/DATABASE_SUMMARY.md` for the
analogous case in `reset_portfolio`). Full-repo coverage (`pytest
--cov=app --cov-report=term-missing`, 208 tests): **96%**; `app/api/
history.py` is 100%, `app/market/cache.py` 98% (one unreachable defensive
branch), `app/market/models.py` 100%.

One flaky test surfaced only under coverage instrumentation's added
overhead and was fixed: `test_snapshot_loop_runs_periodically_until_cancelled`
used a fixed `sleep(0.05)` against a `0.01`s loop interval, which is a
timing assumption that doesn't hold when execution is slower (coverage
tracing, a loaded CI box). Rewrote it to poll for the expected snapshot
count with a generous bounded timeout instead of a fixed sleep. Confirmed
green both with and without `--cov` afterward.

## Constraints honored

- `backend/app/db/` untouched, including its tests.
- `backend/app/market/` was touched, but only as explicitly directed by
  the coordinator in two follow-up messages, scoped to exactly
  `cache.py` (ring buffer + open-price tracking) and `models.py`
  (`PriceUpdate`'s new optional field + properties) — both
  backward-compatible additions (new fields default to values that
  reproduce the old behavior; nothing existing was renamed, removed, or
  had its signature changed in a breaking way). `app/market/stream.py`,
  `simulator.py`, `massive_client.py`, `factory.py`, `interface.py`,
  `seed_prices.py`, and every existing test under `tests/market/` were
  **not** modified — new behavior was added via new test files instead of
  editing the pre-existing ones, per the pattern already established by
  `planning/DATABASE_SUMMARY.md` for its own seed-resurrection fix. The
  full pre-existing 73-test market suite still passes unmodified.
- `backend/app/db/repository.py`'s `execute_trade` price argument is
  always supplied by looking up `PriceCache` in `app/api/portfolio.py` —
  `app/db` still has no import of `app/market`.
- `app/api/chat.py` was not touched (owned by the LLM Engineer in
  parallel); `app/api/__init__.py` only gained one more router import
  (`history`) alongside the pre-existing `chat` import.
- `frontend/`, `Dockerfile`, `scripts/` untouched.
- Did not run `git commit` — left for review as instructed.

## Files touched

- `backend/app/portfolio/__init__.py`, `valuation.py`, `tracking.py`,
  `snapshotter.py` (new)
- `backend/app/api/__init__.py`, `deps.py`, `schemas.py`, `errors.py`,
  `health.py`, `portfolio.py`, `watchlist.py`, `trades.py`, `chat.py`,
  `history.py` (new; `chat.py` untouched after creation, per scope)
- `backend/app/main.py` (new)
- `backend/app/market/cache.py`, `models.py` (modified — follow-up
  additions, see above; not new files)
- `backend/tests/portfolio/__init__.py`, `conftest.py`,
  `test_valuation.py`, `test_tracking.py`, `test_snapshotter.py` (new)
- `backend/tests/api/__init__.py`, `conftest.py`, `test_health.py`,
  `test_watchlist.py`, `test_portfolio.py`, `test_trades.py`,
  `test_chat.py`, `test_static_mount.py`, `test_history.py` (new)
- `backend/tests/market/test_cache_history.py`,
  `test_cache_day_change.py`, `test_models_day_change.py` (new; the
  pre-existing `test_cache.py`/`test_models.py` were not edited)
- `backend/pyproject.toml` (added `httpx` to the `dev` extra — required by
  `fastapi.testclient.TestClient`)
- `planning/API_CONTRACT.md`, `planning/BACKEND_SUMMARY.md` (new, then
  updated twice for the two follow-ups)

No files outside `backend/app/api/` (excluding `chat.py`'s body),
`backend/app/portfolio/`, `backend/app/main.py`,
`backend/app/market/cache.py`, `backend/app/market/models.py`,
`backend/tests/api/`, `backend/tests/portfolio/`, `backend/tests/market/`
(new files only), `backend/pyproject.toml`, and these two planning docs
were created or modified. `frontend/`, `Dockerfile`, and `scripts/` were
never touched.
