# FinAlly — API Contract

Status: **implemented** (except `POST /api/chat`, which is registered and
documented here but its handler is a stub — see that section). This is the
contract the Frontend Engineer and LLM Engineer code against. If you need a
shape that isn't here, that's a bug in this document — flag it to the
Backend API Engineer rather than guessing.

Implementation: `backend/app/api/` (routers), `backend/app/portfolio/`
(valuation/tracking/snapshot logic), `backend/app/main.py` (app assembly).
Tests: `backend/tests/api/`, `backend/tests/portfolio/`.

## Conventions (binding, apply to every endpoint below)

- **Base URL**: everything is same-origin, under `/api/*`. `GET
  /api/stream/prices` (SSE) is owned by the market data component — see
  `planning/MARKET_DATA_SUMMARY.md`; it is not repeated here except where
  it interacts with these endpoints (A4).
- **Timestamps (A6)**: every timestamp in a REST JSON response is an ISO
  8601 string in UTC, e.g. `"2026-09-08T12:00:00.123456+00:00"` (Python's
  `datetime.now(UTC).isoformat()`). The only place epoch-seconds floats
  appear is inside SSE payloads from `/api/stream/prices` — never in a
  response from an endpoint in this document.
- **Errors (C5)**: every 4xx/5xx response body is `{"detail": <value>}`.
  For endpoints in this file, `<value>` is a plain string in the large
  majority of cases. The one exception: FastAPI's automatic request-body
  validation errors (malformed JSON, wrong types, a `side` value other than
  `"buy"`/`"sell"`) return HTTP 422 with `{"detail": "<field>: <message>"}`
  — still a string, just possibly prefixed with the offending field path.
  There is exactly one error shape to handle on the frontend: read
  `response.json().detail` as a string and display it.
- **Mutating endpoints return updated state (C2)**: `POST
  /api/portfolio/trade`, `POST /api/portfolio/reset`, `POST
  /api/watchlist`, and `DELETE /api/watchlist/{ticker}` all return the
  full updated resource(s) in the response body. Never issue a follow-up
  GET after one of these calls.
- **Watchlist responses never include price (C3)**. `GET /api/watchlist`,
  and the `watchlist` array embedded in trade/reset responses, contain only
  `ticker` and `added_at`. Prices come exclusively from `/api/stream/prices`.
- **Ticker normalization**: every endpoint that accepts a ticker (in a
  body or path) strips whitespace and uppercases it before use, and
  rejects anything that doesn't match `^[A-Z][A-Z0-9.\-]{0,9}$` (1–10
  chars, starts with a letter, remainder letters/digits/`.`/`-` — covers
  things like `V`, `AAPL`, `BRK.B`) with `400 {"detail": "Invalid ticker
  format: ..."}`. This is a format check only, not a real-symbol
  allowlist, per PLAN §13.B3.
- **total_value (B6)**: defined once, as `cash_balance + sum(quantity *
  current_price)` over open positions, where `current_price` comes from
  the live `PriceCache`. A position whose ticker has no cached price yet
  (just bought, before the market source has ticked it) is **excluded**
  from the sum — never valued at 0 or at `avg_cost`. Every response below
  that includes `total_value` or per-position `market_value`/
  `unrealized_pnl`/`unrealized_pnl_percent` uses this same function
  (`app.portfolio.compute_total_value` / `build_position_view`); those
  fields are `null` (not `0`) when there's no cached price yet.
- **Tracked tickers (A4)**: the market data source is always kept pricing
  exactly `watchlist ∪ {tickers with a non-zero position}`. Every endpoint
  that changes the watchlist or executes a trade re-syncs this
  automatically; the frontend/LLM engineer never needs to call
  `add_ticker`/`remove_ticker` directly (there's no such endpoint — it's
  an internal market-data-source method, not a route).

---

## System

### `GET /api/health`

Health check. Always 200 once the process is up.

**Response `200`**
```json
{"status": "ok"}
```

---

## Portfolio

### `GET /api/portfolio`

Current cash, positions (with live P&L), and total value.

**Response `200`**
```json
{
  "cash_balance": 8000.0,
  "total_value": 10120.0,
  "positions": [
    {
      "ticker": "AAPL",
      "quantity": 10.0,
      "avg_cost": 200.0,
      "current_price": 212.0,
      "market_value": 2120.0,
      "unrealized_pnl": 120.0,
      "unrealized_pnl_percent": 6.0,
      "updated_at": "2026-09-08T12:00:00+00:00"
    }
  ],
  "updated_at": "2026-09-08T12:00:05.001+00:00"
}
```
- `positions` is `[]` when flat, ordered by ticker ascending.
- `current_price` / `market_value` / `unrealized_pnl` /
  `unrealized_pnl_percent` are `null` (all four together) when the ticker
  has no cached price yet.
- `updated_at` at the top level is when this response was computed (not a
  DB column) — safe to use as a "last refreshed" timestamp.

No error cases specific to this endpoint (barring 5xx).

### `POST /api/portfolio/trade`

Execute a market order. Instant fill at the current cached price, no fees.

**Request**
```json
{"ticker": "AAPL", "side": "buy", "quantity": 10}
```
- `ticker`: string, 1–10 chars (format-validated as above).
- `side`: `"buy"` or `"sell"` — anything else is a 422 validation error.
- `quantity`: number, must be a **positive, finite** value (B4). `0`,
  negative, `NaN`, `Infinity` are all rejected with `400`.

**Response `200`**
```json
{
  "trade": {
    "id": "3f9e...",
    "ticker": "AAPL",
    "side": "buy",
    "quantity": 10.0,
    "price": 200.0,
    "executed_at": "2026-09-08T12:00:00+00:00"
  },
  "portfolio": { "...": "same shape as GET /api/portfolio" }
}
```

**Errors**
| Status | When | `detail` |
|---|---|---|
| 400 | `ticker` fails format validation | `"Invalid ticker format: ..."` |
| 400 | `quantity <= 0` or non-finite | `"quantity must be a positive, finite number"` |
| 400 | No cached price yet for `ticker` (B4 — a just-added symbol before its first tick; the trade is rejected rather than filled at 0) | `"No live price available for {ticker} yet; add it to the watchlist and wait for the next tick before trading it"` |
| 400 | Buy exceeds cash on hand | `"Insufficient cash: required X, available Y"` |
| 400 | Sell exceeds shares held | `"Insufficient shares: requested X, held Y"` |
| 422 | `side` not `"buy"`/`"sell"`, missing field, wrong type | pydantic-derived message |

**Side effects, always on success:**
1. `app.db.execute_trade` runs (cash + position updated, a `trades` row
   appended) inside its own transaction.
2. If `ticker` wasn't already on the watchlist, it is added (B4 — "trading
   a ticker not on the watchlist auto-adds it").
3. The market data source is re-synced to the current tracked-ticker set
   (A4) — matters when a sell fully closes a position in a ticker that
   isn't watchlisted, which then stops being priced.
4. A `portfolio_snapshots` row is recorded immediately, using the same
   `total_value` definition as everywhere else (PLAN §7's "immediately
   after each trade execution").

### `GET /api/portfolio/history`

Portfolio value over time, for the P&L chart. Bounded per B2 — never an
unbounded scan of `portfolio_snapshots`.

**Query params**
| Name | Type | Default | Notes |
|---|---|---|---|
| `since` | ISO 8601 string | none | Only snapshots at/after this timestamp. `400` if not parseable by `datetime.fromisoformat`. |
| `limit` | int | `200` | `1 <= limit <= 2000` (422 if outside — FastAPI `Query(ge=1, le=2000)`). |

**Response `200`**
```json
{
  "snapshots": [
    {"total_value": 10000.0, "recorded_at": "2026-09-08T12:00:00+00:00"},
    {"total_value": 10032.5, "recorded_at": "2026-09-08T12:00:30+00:00"}
  ]
}
```
Ordered oldest → newest (ready to feed directly into a line chart).

### `POST /api/portfolio/reset`

Restores the account to a fresh install: cash back to $10,000, all
positions/trades/snapshots/**chat history** deleted, watchlist replaced
with the 10 defaults (this mirrors `app.db.reset_portfolio` — chat history
is cleared too; that's a deliberate full-reset judgment call inherited from
the DB layer, not a partial one, per `planning/DATABASE_SUMMARY.md`).

**Request**: no body.

**Response `200`**
```json
{
  "portfolio": { "...": "same shape as GET /api/portfolio, now empty/10000" },
  "watchlist": [
    {"ticker": "AAPL", "added_at": "2026-09-08T12:00:00+00:00"},
    "... 9 more, the PLAN §7 defaults"
  ]
}
```
Also re-syncs the market data source (A4) and records one snapshot
immediately after the reset.

---

## Watchlist

### `GET /api/watchlist`

**Response `200`**
```json
{
  "watchlist": [
    {"ticker": "AAPL", "added_at": "2026-09-08T00:00:00+00:00"}
  ]
}
```
No price fields (C3). Ordered by `added_at` ascending.

### `POST /api/watchlist`

Add a ticker. **Idempotent**: adding an already-present ticker returns
`200` with the unchanged list, not a `409`.

**Request**
```json
{"ticker": "PYPL"}
```

**Response `200`**: same shape as `GET /api/watchlist`, post-add.

**Errors**
| Status | When |
|---|---|
| 400 | Ticker fails format validation |
| 422 | Missing/wrong-typed `ticker`, or over 10 chars |

Side effect: market data source synced (A4) — the new ticker starts
pricing on its next tick.

### `DELETE /api/watchlist/{ticker}`

Remove a ticker from the watchlist. `{ticker}` is normalized the same way
as elsewhere (case-insensitive).

**Response `200`**: same shape as `GET /api/watchlist`, post-removal.

**Errors**
| Status | When | `detail` |
|---|---|---|
| 404 | Ticker wasn't on the watchlist | `"{TICKER} is not on the watchlist"` |
| 400 | Ticker fails format validation | `"Invalid ticker format: ..."` |

Side effect: market data source synced (A4). **If the ticker is still
held (non-zero position), it keeps being priced** — removing it from the
watchlist does not stop its price feed while a position is open. It stops
once the position is fully closed (whether that happens via a later sell,
or was already the case).

---

## Trades

### `GET /api/trades`

The trade blotter (PLAN §13.B1 — the `trades` table, otherwise
write-only). Bounded like history.

**Query params**: `limit` (int, default `100`, `1 <= limit <= 1000`, 422
outside that range).

**Response `200`**
```json
{
  "trades": [
    {
      "id": "3f9e...",
      "ticker": "AAPL",
      "side": "buy",
      "quantity": 10.0,
      "price": 200.0,
      "executed_at": "2026-09-08T12:00:00+00:00"
    }
  ]
}
```
Ordered most-recent-first (matches `app.db.get_trades`).

---

## Chat

### `GET /api/chat/history`

**Query params**: `limit` (int, default `20`, clamped silently to
`[1, 200]` — no error on out-of-range, unlike the other `limit` params;
this endpoint is meant to be called with a fixed small page size by the
chat panel on load).

**Response `200`**
```json
{
  "messages": [
    {
      "id": "a1b2...",
      "role": "user",
      "content": "buy 10 AAPL",
      "actions": null,
      "created_at": "2026-09-08T12:00:00+00:00"
    },
    {
      "id": "c3d4...",
      "role": "assistant",
      "content": "Done — bought 10 AAPL at $200.00.",
      "actions": {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10, "status": "success"}]},
      "created_at": "2026-09-08T12:00:01+00:00"
    }
  ]
}
```
Ordered oldest → newest. `actions` is `null` for user messages; for
assistant messages it's whatever JSON object was stored (parsed from the
DB's `actions` TEXT column — the API layer does `json.loads`, the caller
never sees a stringified-JSON-inside-JSON value).

### `POST /api/chat` — **STUB, not yet implemented**

The route is registered (`backend/app/api/chat.py`) and validates its
request body, but the handler currently always returns:

**Response `501`**
```json
{"detail": "Chat is not yet implemented. See planning/API_CONTRACT.md for the target contract."}
```

**Request contract (already enforced)**
```json
{"message": "Should I buy more AAPL?"}
```
`message`: non-empty string (422 if empty/missing).

**Target response contract for the LLM Engineer to implement** (not yet
built — this is the spec, not the current behavior):

```json
{
  "message": "I'll buy 10 AAPL at the current price.",
  "trades_executed": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10.0, "price": 200.0, "status": "success"}
  ],
  "trades_failed": [
    {"ticker": "TSLA", "side": "buy", "quantity": 1000, "status": "failed", "error": "Insufficient cash: required 250000.00, available 8000.00"}
  ],
  "watchlist_changes": [
    {"ticker": "PYPL", "action": "add", "status": "success"}
  ],
  "portfolio": { "...": "same shape as GET /api/portfolio" },
  "watchlist": { "...": "same shape as GET /api/watchlist" }
}
```

Design notes the LLM Engineer must follow (from PLAN §13.A3, decision
(a)):
- **The LLM cannot know whether a trade will succeed before it writes
  `message`.** Word the system prompt so the model never claims a trade is
  *done* in `message` itself (say "I'll buy..." not "I bought..."); the
  *actual* outcome is reported in the separate `trades_executed` /
  `trades_failed` blocks, which the frontend renders as inline
  confirmation/error chips distinct from the prose. Do not make a second
  LLM call to "fix" the message after execution — one call, structured
  execution results alongside it.
- **Reuse this file's validated paths, don't reimplement them.** Each
  trade in `trades` from the structured LLM output should go through the
  exact same checks as `POST /api/portfolio/trade` in this document
  (ticker format, positive finite quantity, price-cache presence,
  `app.db.execute_trade`, watchlist auto-add, tracked-ticker sync, and an
  immediate snapshot) — call the same Python functions
  (`app.portfolio.sync_tracked_tickers`, `app.portfolio.snapshot_once`,
  `app.db.execute_trade`, `app.db.add_to_watchlist`) rather than
  duplicating the logic. Same for `watchlist_changes` against
  `app.db.add_to_watchlist` / `remove_from_watchlist`.
- Persist both the user message and the assistant message via
  `app.db.add_chat_message` (`actions` = `json.dumps(...)` of whatever
  subset of `trades_executed`/`trades_failed`/`watchlist_changes` actually
  ran; `None` for the user's own message).
- Return the post-execution `portfolio`/`watchlist` per C2, exactly like
  the other mutating endpoints in this file.

---

## What's deliberately NOT an endpoint

- There is no `POST`/`DELETE` for individual ticker price tracking — that
  is an internal effect of watchlist/trade endpoints (A4), not something
  the frontend calls directly.
- There is no endpoint to fetch a single position — use `GET
  /api/portfolio` and filter client-side; the position count is small
  (bounded by watchlist size) and this avoids a second total_value
  definition.
