# FinAlly — Database Layer Summary

Status: **done**. Implements PLAN.md §7 and the binding review decisions
C1, B7, B9, B5 (plus B1's `POST /api/portfolio/reset` and B4's price-
validation requirement, added after initial design per teammate feedback).
Full contract detail (schema DDL, exact repository signatures, concurrency
rationale) lives in `planning/archive/DATABASE_DESIGN.md`, moved there now
that this summary is the current reference, following the pattern
established by the market data component.

## What was built

```
backend/app/db/
    __init__.py     Public API surface (import from here, not submodules)
    connection.py   get_db_path(), get_connection() context manager,
                    lazy schema init + gated seeding
    schema.py       SCHEMA_SQL — six CREATE TABLE IF NOT EXISTS + indexes
    seed.py         DEFAULT_CASH_BALANCE, DEFAULT_WATCHLIST, seed_defaults()
    models.py       Frozen dataclasses: UserProfile, WatchlistItem, Position,
                    Trade, PortfolioSnapshot, ChatMessage, TradeResult
    errors.py       DBError, InvalidTradeError, InsufficientCashError,
                    InsufficientSharesError
    repository.py   14 async functions (below) + their private _sync_* cores

backend/tests/db/
    conftest.py               per-test DATABASE_PATH via tmp_path + monkeypatch
    test_seed_and_init.py     fresh-DB seeding, idempotent re-init, WAL mode,
                              check_same_thread=False, the seed-resurrection
                              regression (below)
    test_repository.py        watchlist/positions/trades/snapshots/chat/reset,
                              trade validation, weighted avg_cost, float-
                              residual position deletion
    test_trade_concurrency.py concurrent buys/sells against BEGIN IMMEDIATE
```

## Repository API — exact signatures (import `from app.db import ...`)

```python
DEFAULT_USER_ID: str = "default"

async def init_db() -> None
async def get_user_profile(user_id: str = DEFAULT_USER_ID) -> UserProfile
async def get_cash_balance(user_id: str = DEFAULT_USER_ID) -> float
async def get_watchlist(user_id: str = DEFAULT_USER_ID) -> list[WatchlistItem]
async def add_to_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> WatchlistItem
async def remove_from_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> bool
async def get_positions(user_id: str = DEFAULT_USER_ID) -> list[Position]
async def get_position(ticker: str, user_id: str = DEFAULT_USER_ID) -> Position | None
async def execute_trade(
    ticker: str, side: str, quantity: float, price: float,
    user_id: str = DEFAULT_USER_ID,
) -> TradeResult
async def get_trades(user_id: str = DEFAULT_USER_ID, limit: int = 100) -> list[Trade]
async def record_snapshot(total_value: float, user_id: str = DEFAULT_USER_ID) -> PortfolioSnapshot
async def get_snapshots(
    user_id: str = DEFAULT_USER_ID, since: str | None = None, limit: int = 500,
) -> list[PortfolioSnapshot]
async def add_chat_message(
    role: str, content: str, actions: str | None = None, user_id: str = DEFAULT_USER_ID,
) -> ChatMessage
async def get_chat_history(user_id: str = DEFAULT_USER_ID, limit: int = 20) -> list[ChatMessage]
async def reset_portfolio(user_id: str = DEFAULT_USER_ID) -> None
```

`TradeResult` = `(trade: Trade, position: Position | None, cash_balance: float)`.
`Position | None` on `TradeResult.position` and `get_position()` is `None`
exactly when the position was fully closed / never opened.

`DBError` subclasses (`InvalidTradeError`, `InsufficientCashError`,
`InsufficientSharesError`) are raised, never returned as sentinels — map
them to `{"detail": "..."}` 4xx responses in the API layer (C5).

## Endpoint coverage check (PLAN §8 + §13.B1)

| Endpoint | Repository function(s) |
|---|---|
| `GET /api/portfolio` | `get_user_profile`, `get_positions` |
| `POST /api/portfolio/trade` | `execute_trade` |
| `GET /api/portfolio/history` | `get_snapshots` |
| `POST /api/portfolio/reset` | `reset_portfolio` |
| `GET /api/watchlist` | `get_watchlist` |
| `POST /api/watchlist` | `add_to_watchlist` |
| `DELETE /api/watchlist/{ticker}` | `remove_from_watchlist` |
| `GET /api/trades` | `get_trades` |
| `POST /api/chat` (persistence) | `add_chat_message` |
| `GET /api/chat/history` | `get_chat_history` |

Every endpoint named in §8 and in the §13.B1 gap list has a corresponding
function. Nothing is missing.

## Binding decisions — how each was implemented

- **C1**: all code is under `backend/app/db/`. Nothing was added to
  `backend/db/` (which doesn't exist) or outside the assigned paths.
- **B7**: `get_db_path()` reads `DATABASE_PATH` fresh on every call (not
  cached), defaulting to `<repo_root>/db/finally.db`; the container sets
  `DATABASE_PATH=/app/db/finally.db` via its own environment (outside this
  module's concern).
- **B9**: `PRAGMA journal_mode=WAL`, `check_same_thread=False`, one
  connection opened per call (no shared pooled connection across
  threadpool workers), `isolation_level=None` so the code controls
  transactions explicitly, `PRAGMA busy_timeout=5000`. Every public
  function is `async def` and dispatches its blocking `_sync_*`
  implementation via `asyncio.to_thread`. `execute_trade` wraps the
  cash-balance read + position read/write + trade insert in one
  `BEGIN IMMEDIATE ... COMMIT` (or `ROLLBACK` on any exception),
  serializing concurrent trades against the same account. Verified under
  real thread concurrency in `test_trade_concurrency.py` (20 concurrent
  buys lose no updates; concurrent overlapping sells: exactly one of two
  succeeds, never both).
- **B5**: cash is rounded to cents (`round(x, 2)`) on every write, and so is
  trade notional before being applied to cash. A position row is deleted
  when the resulting `abs(quantity) < 1e-9` rather than left with float
  noise. `avg_cost` is recomputed only on buys (quantity-weighted average of
  old position + new lot); sells never touch it.
- **B4 (price validation, raised mid-task)**: `execute_trade` validates
  `price` itself (`math.isfinite` and `> 0`) and raises `InvalidTradeError`
  for `0`, negative, `NaN`, or `inf` — it will not silently fill a trade at
  a nonsensical price. The Backend API Engineer still owns the decision of
  *whether a price exists at all*: look up the ticker in `PriceCache`
  first and reject the trade before ever calling `execute_trade` if there's
  no cached price yet (a just-added ticker with no tick). This division of
  responsibility is spelled out in `planning/archive/DATABASE_DESIGN.md` §7.
- **B1 (reset endpoint, raised mid-task)**: `reset_portfolio()` added —
  restores `cash_balance` to 10000.0, deletes all positions/trades/
  portfolio_snapshots/chat_messages rows, and replaces the watchlist with
  exactly the ten defaults, all inside one `BEGIN IMMEDIATE` transaction.
  Chat history is cleared too (treated as a full fresh-install reset, not a
  partial one) — flag this to the Backend API Engineer if they expect chat
  to survive a reset, since it's a judgment call, not a PLAN.md requirement.

## A bug found and fixed during testing

The first implementation ran seeding (`INSERT OR IGNORE` of the default
profile + watchlist) unconditionally on every connection open. That's wrong:
once a user deletes a default watchlist ticker, there's no longer a
unique-constraint conflict for `OR IGNORE` to catch, so the very next
connection would silently resurrect the deleted ticker. Fixed by gating
seeding on `users_profile` having zero rows (i.e., seeding now only ever
runs once per database's lifetime); schema creation (`CREATE TABLE IF NOT
EXISTS`) still runs on every open, which remains safely idempotent. Caught
by `test_remove_from_watchlist_returns_true_when_present`; a dedicated
regression test (`test_removed_default_ticker_is_not_resurrected`) now
guards it.

## Test results (real output, not a description of intent)

```
$ uv run --extra dev pytest -q          # from backend/
132 passed in 2.22s
```
(59 new tests in `tests/db/`, 73 pre-existing in `tests/market/`, all
passing — no regressions to the market data suite.)

```
$ uv run --extra dev ruff check app/ tests/
All checks passed!
```

Coverage of the new module (`uv run --extra dev pytest tests/db
--cov=app.db --cov-report=term-missing`): **99%** (309/312 statements; the
3 missed lines are the `except`/`ROLLBACK` branch inside `reset_portfolio`,
which requires injecting a failure mid-transaction to exercise and is not
worth the complexity for a rarely-hit defensive path). This exceeds the
market data module's 84% baseline.

## What the Backend API Engineer must supply

- Current price lookups from `app.market.PriceCache` for `execute_trade`'s
  `price` argument and for computing `total_value` before calling
  `record_snapshot` — `app/db/` intentionally has no dependency on
  `app/market/`.
- Rejecting a trade before calling `execute_trade` when the price cache has
  no entry yet for the ticker (see B4 note above).
- Mapping `DBError` subclasses to HTTP error responses.
- Ticker existence/format validation beyond simple normalization
  (strip + uppercase, already done in this layer) — out of scope here per
  PLAN §13.B3.

## Files touched

- `backend/app/db/__init__.py`, `connection.py`, `schema.py`, `seed.py`,
  `models.py`, `errors.py`, `repository.py` (new)
- `backend/tests/db/__init__.py`, `conftest.py`, `test_seed_and_init.py`,
  `test_repository.py`, `test_trade_concurrency.py` (new)
- `planning/DATABASE_DESIGN.md` → moved to `planning/archive/DATABASE_DESIGN.md`
- `planning/DATABASE_SUMMARY.md` (this file, new)

No files outside `backend/app/db/`, `backend/tests/db/`, and these two
planning docs were created or modified.
