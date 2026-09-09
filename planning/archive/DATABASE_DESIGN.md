# FinAlly — Database Design

Author: Database Engineer. Status: **contract — implement against this**.

This document specifies the schema, the repository API exposed to the Backend
API Engineer, and the connection/concurrency approach for `backend/app/db/`.
It resolves PLAN.md §7 plus the binding review decisions C1, B7, B9, B5 (and
touches B3 for ticker normalization, B6 for the `total_value` formula
ownership boundary).

Code will live at `backend/app/db/` (never `backend/db/` — C1). The top-level
`db/` directory remains purely the runtime volume mount for the SQLite file.

---

## 1. Tables

Six tables, exactly as PLAN.md §7 describes, created with `CREATE TABLE IF
NOT EXISTS` (safe to run on every connection open):

```sql
CREATE TABLE IF NOT EXISTS users_profile (
    id           TEXT PRIMARY KEY,
    cash_balance REAL NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id        TEXT PRIMARY KEY,
    user_id   TEXT NOT NULL DEFAULT 'default',
    ticker    TEXT NOT NULL,
    added_at  TEXT NOT NULL,
    UNIQUE (user_id, ticker)
);

CREATE TABLE IF NOT EXISTS positions (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL DEFAULT 'default',
    ticker     TEXT NOT NULL,
    quantity   REAL NOT NULL,
    avg_cost   REAL NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, ticker)
);

CREATE TABLE IF NOT EXISTS trades (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL DEFAULT 'default',
    ticker       TEXT NOT NULL,
    side         TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity     REAL NOT NULL,
    price        REAL NOT NULL,
    executed_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trades_user_executed
    ON trades (user_id, executed_at);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL DEFAULT 'default',
    total_value  REAL NOT NULL,
    recorded_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_user_recorded
    ON portfolio_snapshots (user_id, recorded_at);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL DEFAULT 'default',
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    actions     TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_user_created
    ON chat_messages (user_id, created_at);
```

All timestamps are ISO 8601 UTC strings (`datetime.now(timezone.utc).isoformat()`),
consistent with A6's recommendation for the REST/DB boundary. `id` columns are
`str(uuid4())`. `user_id` is always `"default"` today (single-user); every
repository function accepts `user_id: str = DEFAULT_USER_ID` so multi-user is
a parameter change, not a migration, later.

**`total_value` is not computed by this layer.** Per B6 it is
`cash_balance + Σ(quantity × current_price)`, and `current_price` comes from
the market data `PriceCache`, which this module does not import (clean
separation — `app/db/` has no dependency on `app/market/`). The Backend API
Engineer computes `total_value` and calls `record_snapshot(total_value)`.

## 2. Seed defaults

On first use (empty `users_profile`):
- One profile: `id="default"`, `cash_balance=10000.0`.
- Ten watchlist rows: `AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX`.

Seeding uses `INSERT OR IGNORE` keyed on the table's natural unique
constraint (`users_profile.id`, `watchlist(user_id, ticker)`), so it is safe
to run unconditionally on every connection open — already-seeded rows are
simply skipped. This is what makes re-init idempotent without a separate
"have I seeded?" flag or race-prone check-then-insert.

## 3. Lazy-init flow

There is no separate migration step and no explicit "first request" hook
required by callers. Every time a connection is opened (i.e., on every
repository call), the connection helper:

1. Runs the six `CREATE TABLE IF NOT EXISTS` statements (+ indexes).
2. Checks whether `users_profile` has zero rows; **only if so**, runs the
   `INSERT OR IGNORE` seed statements (default profile + ten watchlist
   rows).

Step 1 is cheap and fully idempotent on its own. Step 2's seeding is
deliberately gated on "the profile table is empty" rather than run
unconditionally: `INSERT OR IGNORE` alone is not sufficient to make seeding
safe to repeat, because once a user deletes a default watchlist ticker
there is no longer a unique-constraint conflict for `OR IGNORE` to catch —
an unconditional re-seed on the very next connection would silently
resurrect it. Gating on an empty profile table means seeding truly only
ever happens once per database's lifetime, while both steps still run on
every connection open with no in-process "already initialized" flag to
maintain — which would otherwise misbehave if `DATABASE_PATH` changes
mid-process (as it does across pytest tests using different tmp files). A
fresh Docker volume, a deleted file, or a mid-test-suite path swap all
converge to the correct state on the very next call.

`init_db() -> None` (async) is also exposed for callers who want to force
initialization eagerly (e.g., a FastAPI startup hook, so the first real
request isn't the one paying schema-creation cost) but calling it is
optional — every other repository function triggers the same lazy path.

## 4. Connection & concurrency approach (B9)

- **WAL mode**: `PRAGMA journal_mode=WAL` set on every connection.
- **`check_same_thread=False`**: connections may be created and used from
  threadpool worker threads (not the event loop thread).
- **One connection per call, not a shared pool.** Each repository call opens
  its own `sqlite3.connect(...)`, does its work, and closes it. This avoids
  the hazards of sharing one `sqlite3.Connection` object across concurrent
  threadpool workers (the module warns the same connection object should not
  run concurrent statements from different threads even with
  `check_same_thread=False`). Concurrency across calls is arbitrated by
  SQLite's own file locking plus `PRAGMA busy_timeout=5000` (retry for up to
  5s before raising `sqlite3.OperationalError` on lock contention), which is
  ample for single-user trade-sized transactions.
- **`isolation_level=None`** (Python sqlite3 "autocommit" mode) on every
  connection. This hands full transaction control to our code instead of
  the driver's implicit-BEGIN-before-DML behavior, which is required to
  issue explicit `BEGIN IMMEDIATE` (mixing the driver's implicit transactions
  with explicit `BEGIN` raises `OperationalError: cannot start a transaction
  within a transaction`).
- **Async dispatch**: every public repository function is `async def` and
  internally does `await asyncio.to_thread(_sync_impl, ...)`. The actual
  blocking sqlite3 work lives in a private `_sync_*` function; the public
  async function is a thin threadpool-dispatching wrapper. This is what
  keeps the event loop (and therefore the SSE stream) from stalling on DB
  I/O, per B9. `_sync_*` functions are also unit-tested directly (no event
  loop needed) for the concurrency test.
- **`BEGIN IMMEDIATE` around the trade read-modify-write**: `execute_trade`
  acquires a `RESERVED` lock up front (`BEGIN IMMEDIATE`), then reads
  `cash_balance` + the position row, validates, writes the new cash balance,
  upserts/deletes the position row, and inserts the trade row, then
  `COMMIT`s — all on one connection, one transaction. This closes the
  check-then-act race described in B9: a second concurrent buy cannot read
  a stale cash balance while the first is still mid-transaction, because
  `BEGIN IMMEDIATE` blocks it (up to `busy_timeout`) until the first
  transaction resolves.

## 5. Money / float rules (B5)

- Cash is rounded to cents (`round(x, 2)`) on every write.
- Trade notional (`quantity * price`) is rounded to cents before being
  applied to cash.
- A position is deleted (row removed) when the resulting `abs(quantity) <
  1e-9`, rather than left as a float-noise residual (e.g., a sell of "all
  shares" that leaves `quantity == -3.5e-14` due to float subtraction).
- `avg_cost` is recomputed only on **buys** — weighted average of old
  position and the new lot:
  `new_avg = (old_qty * old_avg_cost + buy_qty * price) / (old_qty + buy_qty)`.
  **Sells never change `avg_cost`.** Realized P&L is intentionally not
  tracked (per B5); it surfaces implicitly via `cash_balance` and the
  `portfolio_snapshots` value curve.

## 6. Errors

Defined in `app/db/errors.py`, all subclassing `DBError(Exception)`:

- `InvalidTradeError` — non-finite/non-positive `quantity` or `price`, or
  `side` not in `{"buy", "sell"}`. **This module validates `price` itself
  and raises rather than trusting the caller** — but the *responsibility*
  for deciding whether a price exists at all belongs to the caller: the
  Backend API Engineer must look up the ticker in `PriceCache` first and
  reject the trade (before ever calling `execute_trade`) if there is no
  cached price yet (a just-added ticker with no tick), per PLAN §13.B4.
  Passing `0`, a negative number, `NaN`, or `inf` through to `execute_trade`
  as a stand-in for "no price" will raise `InvalidTradeError`, not silently
  fill at that price.
- `InsufficientCashError(required: float, available: float)` — buy would
  overdraw cash.
- `InsufficientSharesError(requested: float, held: float)` — sell exceeds
  held quantity (a small epsilon, `1e-9`, is tolerated so "sell everything"
  requests that pass exactly `held` never spuriously fail on float noise).

The Backend API Engineer catches these in the route handler and maps them to
`{"detail": "..."}` 400 responses (per C5); this module raises, it never
returns an error sentinel.

## 7. Repository API — exact signatures

Import as:

```python
from app.db import (
    DEFAULT_USER_ID,
    UserProfile, WatchlistItem, Position, Trade, PortfolioSnapshot, ChatMessage,
    TradeResult,
    DBError, InvalidTradeError, InsufficientCashError, InsufficientSharesError,
    init_db, get_user_profile, get_cash_balance,
    get_watchlist, add_to_watchlist, remove_from_watchlist,
    get_positions, get_position,
    execute_trade, get_trades,
    record_snapshot, get_snapshots,
    add_chat_message, get_chat_history,
    reset_portfolio,
)
```

All functions are `async def`. All accept `user_id: str = DEFAULT_USER_ID`
as the final keyword parameter (omitted below for brevity where obvious —
shown in full on the first entry).

```python
async def init_db() -> None:
    """Force schema creation + seeding now. Optional — every call below
    triggers the same lazy init if it hasn't happened yet."""

async def get_user_profile(user_id: str = DEFAULT_USER_ID) -> UserProfile:
    """Fetch the user's profile row. Always exists after lazy init."""

async def get_cash_balance(user_id: str = DEFAULT_USER_ID) -> float:
    """Convenience: just the cash_balance float."""

async def get_watchlist(user_id: str = DEFAULT_USER_ID) -> list[WatchlistItem]:
    """All watchlist rows for the user, ordered by added_at ascending."""

async def add_to_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> WatchlistItem:
    """Add a ticker. Ticker is normalized (stripped, upper-cased) before
    storage. Idempotent: if (user_id, ticker) already exists, returns the
    existing row unchanged rather than raising or duplicating (B3)."""

async def remove_from_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """Remove a ticker (normalized the same way). Returns True if a row was
    deleted, False if it wasn't present. Caller decides whether absence is
    a 404 or a no-op 200."""

async def get_positions(user_id: str = DEFAULT_USER_ID) -> list[Position]:
    """All open positions for the user (quantity != 0 rows only ever
    exist — see B5), ordered by ticker ascending."""

async def get_position(ticker: str, user_id: str = DEFAULT_USER_ID) -> Position | None:
    """Single position by ticker (normalized), or None if not held."""

async def execute_trade(
    ticker: str,
    side: str,            # "buy" | "sell"
    quantity: float,       # must be > 0 and finite; the side conveys direction
    price: float,          # current execution price, supplied by the caller
                           # (this module does not read the market PriceCache)
    user_id: str = DEFAULT_USER_ID,
) -> TradeResult:
    """Execute a market order inside a single BEGIN IMMEDIATE transaction.

    Validates quantity/price/side (raises InvalidTradeError), checks cash
    sufficiency on buys (raises InsufficientCashError) or share sufficiency
    on sells (raises InsufficientSharesError), then atomically updates
    cash_balance, upserts/deletes the position row (deleting when the
    resulting quantity's absolute value is < 1e-9), and appends a trades
    row. Returns the new state; raises and writes nothing on any
    validation failure.
    """

async def get_trades(user_id: str = DEFAULT_USER_ID, limit: int = 100) -> list[Trade]:
    """Trade history, most recent first."""

async def record_snapshot(total_value: float, user_id: str = DEFAULT_USER_ID) -> PortfolioSnapshot:
    """Insert a portfolio_snapshots row with the caller-computed total_value."""

async def get_snapshots(
    user_id: str = DEFAULT_USER_ID,
    since: str | None = None,   # ISO timestamp; if given, only rows with
                                 # recorded_at >= since are returned
    limit: int = 500,
) -> list[PortfolioSnapshot]:
    """Snapshots ordered oldest-first (chronological, ready for a line
    chart). Caller is responsible for choosing a sane `since`/`limit`
    per B2 (this module does not downsample or auto-expire rows)."""

async def add_chat_message(
    role: str,              # "user" | "assistant"
    content: str,
    actions: str | None = None,   # pre-serialized JSON string, or None
    user_id: str = DEFAULT_USER_ID,
) -> ChatMessage:
    """Append a chat message. `actions` is stored verbatim (already-JSON
    text) — this module does not interpret it (C7: deliberate
    denormalization owned by the LLM/API layer)."""

async def get_chat_history(user_id: str = DEFAULT_USER_ID, limit: int = 20) -> list[ChatMessage]:
    """Most recent `limit` messages, returned oldest-first (ready to render
    top-to-bottom). Default of 20 matches the "recent conversation history"
    budget suggested in B10 — callers needing a different budget pass
    `limit` explicitly."""

async def reset_portfolio(user_id: str = DEFAULT_USER_ID) -> None:
    """Restore the user to a fresh-install state, for POST
    /api/portfolio/reset (PLAN §13.B1) and for E2E/integration test
    isolation. In one transaction: sets cash_balance back to 10000.0,
    deletes all positions, trades, and portfolio_snapshots rows, deletes
    all chat_messages rows (a "reset" is a clean-slate demo restart, not a
    partial one), and replaces the watchlist with exactly the ten default
    tickers (any custom adds/removes are discarded). Does not delete or
    recreate the users_profile row itself — it is updated in place, so
    `id="default"` and `created_at` survive a reset."""
```

### Domain types (`app/db/models.py`)

Frozen, slotted dataclasses — one per table, plus `TradeResult`:

```python
@dataclass(frozen=True, slots=True)
class UserProfile:
    id: str
    cash_balance: float
    created_at: str

@dataclass(frozen=True, slots=True)
class WatchlistItem:
    id: str
    user_id: str
    ticker: str
    added_at: str

@dataclass(frozen=True, slots=True)
class Position:
    id: str
    user_id: str
    ticker: str
    quantity: float
    avg_cost: float
    updated_at: str

@dataclass(frozen=True, slots=True)
class Trade:
    id: str
    user_id: str
    ticker: str
    side: str
    quantity: float
    price: float
    executed_at: str

@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    id: str
    user_id: str
    total_value: float
    recorded_at: str

@dataclass(frozen=True, slots=True)
class ChatMessage:
    id: str
    user_id: str
    role: str
    content: str
    actions: str | None
    created_at: str

@dataclass(frozen=True, slots=True)
class TradeResult:
    trade: Trade
    position: Position | None   # None means the position was closed/deleted
    cash_balance: float
```

## 8. `DATABASE_PATH` (B7)

`get_db_path() -> Path` reads `DATABASE_PATH` from the environment on every
call (not cached at import time, so tests can `monkeypatch.setenv` per test
without reloading the module). If unset or blank, it defaults to
`<repo_root>/db/finally.db`, where `repo_root` is resolved relative to this
source file's location (`app/db/connection.py` → up to the repo root),
matching local (non-Docker) development. The container overrides it to
`/app/db/finally.db` via the environment (set in the Dockerfile/compose —
outside this module's concern).

## 9. What the Backend API Engineer must supply

- Current price per ticker for `execute_trade`'s `price` argument, and for
  computing `total_value` before calling `record_snapshot` — both come from
  `app.market.PriceCache`, which this module intentionally does not import.
- Ticker existence/validity checks beyond simple normalization (e.g.,
  whether an unknown symbol should be rejected) — out of scope for
  `app/db/`, per B3, this is a market-data/API-layer concern.
- Mapping `DBError` subclasses to HTTP responses.

---

Backend API Engineer and LLM Engineer: this API surface is ready to code
against. Flag any signature you need changed before I start writing tests
against it, since tests will pin this contract down further.
