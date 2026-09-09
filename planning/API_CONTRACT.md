# FinAlly — API Contract

Status: **implemented** (except `POST /api/chat`, which is registered and
documented here but its handler is a stub — see that section). This is the
contract the Frontend Engineer and LLM Engineer code against. If you need a
shape that isn't here, that's a bug in this document — flag it to the
Backend API Engineer rather than guessing.

Implementation: `backend/app/api/` (routers), `backend/app/portfolio/`
(valuation/tracking/snapshot logic), `backend/app/main.py` (app assembly).
`GET /api/history/{ticker}`, and the `day_change`/`day_change_percent`
fields on the SSE stream, additionally depend on additions to
`backend/app/market/cache.py` (`PriceCache`) and
`backend/app/market/models.py` (`PriceUpdate`) — made by the Backend API
Engineer as two follow-up passes after the original stage-2 brief omitted
them, coordinated with the Market Data Engineer's existing, already-tested
module. Tests: `backend/tests/api/`, `backend/tests/portfolio/`, and
`backend/tests/market/test_cache_history.py` /
`test_cache_day_change.py` / `test_models_day_change.py`.

## Conventions (binding, apply to every endpoint below)

- **Base URL**: everything is same-origin, under `/api/*`. `GET
  /api/stream/prices` (SSE) is owned by the market data component — see
  `planning/MARKET_DATA_SUMMARY.md`; it is not repeated here except where
  it interacts with these endpoints (A4).
- **Timestamps (A6)**: every timestamp in a REST JSON response is an ISO
  8601 string in UTC, e.g. `"2026-09-08T12:00:00.123456+00:00"` (Python's
  `datetime.now(UTC).isoformat()`). The only place epoch-seconds floats
  appear is inside SSE payloads from `/api/stream/prices` — never in a
  response from an endpoint in this document. One endpoint,
  `GET /api/history/{ticker}`, uses a `"...Z"` suffix instead of
  `"...+00:00"` (still ISO 8601 UTC, millisecond precision) to match the
  exact contract the Frontend Engineer is coding against — see that
  section for the precise format.
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

## Market Data

### SSE payload additions: `day_change` / `day_change_percent` (PLAN §13.A1)

`GET /api/stream/prices` itself is unchanged and still owned by the market
data component (`planning/MARKET_DATA_SUMMARY.md`) — this section
documents two new fields inside each ticker's object in that stream's
payload, added by the Backend API Engineer in a follow-up pass because
§13.A1 named this a blocking gap that no stage had implemented.

**Before (still present, unchanged):**
```json
{"AAPL": {"ticker": "AAPL", "price": 190.50, "previous_price": 190.00, "timestamp": 1736342523.5, "change": 0.50, "change_percent": 0.26, "direction": "up"}}
```

**Now (two fields added):**
```json
{"AAPL": {"ticker": "AAPL", "price": 190.50, "previous_price": 190.00, "timestamp": 1736342523.5, "change": 0.50, "change_percent": 0.26, "direction": "up", "day_change": 3.20, "day_change_percent": 1.71}}
```

- `change` / `change_percent` / `direction` are **unchanged** and still
  tick-over-tick (change since the *previous* ~500ms update) — the
  frontend's price-flash animation keys off these, exactly as before.
- `day_change` / `day_change_percent` are **new**: the change from an
  `open_price` captured once per ticker, computed the same way as
  `change`/`change_percent` but against `open_price` instead of
  `previous_price`.
- **What "day" actually means here, precisely, so this is never mistaken
  for a bug**: `open_price` is the price the ticker was first observed at
  by this running process — at process start for the ten seeded
  tickers, or on the first tick after being added later (including a
  re-add after removal, which captures a brand-new open price, not the
  old one). **This is not a true market previous-close.** There is no
  session-open or previous-close concept anywhere in this system. Under
  the simulator (the default), "open price" is simply whatever the GBM
  walk happened to start at when the container booted — restart the
  container and every `day_change` resets to zero from a new baseline.
  Under `MASSIVE_API_KEY` real-data mode, it's still just "price at first
  poll after this process started," not the exchange's actual previous
  close, unless the process happens to have started before that session
  opened. Label it in the UI as something like "since session start," not
  "today's change" or "1D %".
- Both are `0.0` (never an error, `NaN`, or a `ZeroDivisionError`) for a
  ticker with no open price yet or whose open price is `0` — the same
  defensive pattern `change_percent` already uses for `previous_price ==
  0`.
- Implementation: `PriceCache` (`app/market/cache.py`) now tracks
  `open_price` per ticker in a dict separate from the main price map,
  populated on a ticker's first `update()` call and cleared by
  `remove()`. `PriceUpdate` (`app/market/models.py`) gained an optional
  `open_price` field (defaulted to `None`, so every existing call site
  and test that doesn't know about it is unaffected) plus the two new
  computed properties, included in `to_dict()`. `app/market/stream.py`
  (the actual SSE loop) was **not modified** — it already serializes
  whatever `PriceUpdate.to_dict()` returns, so the new fields appear in
  the stream automatically.

### `GET /api/history/{ticker}`

Server-side price history for one ticker — the single source of truth for
both the watchlist sparklines and the main chart (PLAN §13.B13/C4), backed
by a bounded per-ticker ring buffer inside `PriceCache`
(`app/market/cache.py`, `HISTORY_MAXLEN = 600` ticks, about 5 minutes at
the SSE stream's ~500ms cadence). This replaces accumulating history from
`/api/stream/prices` since page load, which emptied on every refresh.

**Path param**: `ticker` — normalized (stripped + uppercased) the same as
everywhere else. No format validation is enforced here (unlike the
watchlist/trade endpoints) — a garbage ticker simply has no history,
handled identically to a real-but-untracked one (see below).

**Query params**: `limit` (int, default `600`, `1 <= limit <= 600` — 600
is both the default *and* the maximum, since the ring buffer never holds
more than that).

**Response `200`**
```json
{
  "ticker": "AAPL",
  "points": [
    {"t": "2026-09-08T19:42:03.500Z", "price": 190.23},
    {"t": "2026-09-08T19:42:04.001Z", "price": 190.31}
  ]
}
```
- `points` is oldest-first, ready to feed directly into a chart.
- `t` is ISO 8601 UTC with millisecond precision and a literal `"Z"`
  suffix — **not** `"+00:00"` like every other timestamp in this document
  (the one deliberate exception to the A6 convention above, to match the
  contract already being built against).
- `price` is a plain float, already rounded to 2dp by `PriceCache`.
- **An unknown ticker, or one with no ticks yet (just added to the
  watchlist, before its first tick from the market data source), returns
  `200` with `"points": []` — not a `404`.** This is a normal, expected
  state the frontend must render as an empty chart, not an error.

**Errors**
| Status | When | `detail` |
|---|---|---|
| 422 | `limit` outside `1..600` | pydantic-derived message (C5's uniform shape still applies — this is the one real error case) |

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
      "content": "I'll buy 10 AAPL at the current price.",
      "actions": {"trades_executed": [{"ticker": "AAPL", "side": "buy", "quantity": 10, "price": 200.0, "status": "success"}]},
      "created_at": "2026-09-08T12:00:01+00:00"
    }
  ]
}
```
Ordered oldest → newest. `actions` is `null` for user messages; for
assistant messages it's whatever JSON object was stored (parsed from the
DB's `actions` TEXT column — the API layer does `json.loads`, the caller
never sees a stringified-JSON-inside-JSON value).

### `POST /api/chat` — **implemented**

`backend/app/api/chat.py`, backed by `backend/app/llm/`. Full design
(system prompt, structured output schema, mock catalogue, context/history
budget) in `planning/LLM_DESIGN.md`.

**Request**
```json
{"message": "Should I buy more AAPL?"}
```
`message`: non-empty string (422 if empty/missing).

**Response contract**:

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
  "portfolio": {
    "cash_balance": 8000.0,
    "total_value": 10120.0,
    "positions": ["... exact shape of GET /api/portfolio's \"positions\" array"],
    "updated_at": "2026-09-08T12:00:05.001+00:00"
  },
  "watchlist": [
    {"ticker": "AAPL", "added_at": "2026-09-08T00:00:00+00:00"}
  ]
}
```
`portfolio` is the exact object `GET /api/portfolio` returns (unwrapped).
`watchlist` is a **bare array** of `{ticker, added_at}` objects — the same
shape `POST /api/portfolio/reset`'s `watchlist` field uses, *not*
`GET /api/watchlist`'s `{"watchlist": [...]}` wrapper. (An earlier draft
of this section used ambiguous `{"...": "same shape as X"}` placeholders
here; that phrasing is what caused the ambiguity — this is the literal
shape, spelled out, to avoid it recurring for the Integration Tester.)

**Errors**
| Status | When | `detail` |
|---|---|---|
| 422 | `message` missing/empty | pydantic-derived message |
| 503 | `OPENROUTER_API_KEY` unset/blank and `LLM_MOCK` isn't `"true"` — the assistant isn't configured at all | `"The AI assistant is not configured: OPENROUTER_API_KEY is missing. ..."` |
| 502 | The real LLM call raised (network error, timeout, non-2xx/insufficient-credits from OpenRouter/Cerebras), or the model's output wasn't recoverable JSON (see below) | `"The AI assistant failed to produce a response. Please try again in a moment."` |

A `502`/`503` is a normal error response (C5's uniform `{"detail": ...}`
shape) — **never** a `200` carrying a synthetic assistant message. A fake
"sorry, something went wrong" chat bubble would be indistinguishable from
a genuine reply and would falsely read as the AI being evasive rather
than the request having failed. On a `503`, nothing is persisted. On a
`502`, the user's own message *is* persisted (`GET /api/chat/history`
will show it), but no assistant turn is written — a synthetic apology
persisted as an assistant message would re-enter the model's own context
window on the next call (it's fed the last 20 stored messages) and the
model would see itself apologizing for something that never happened.

Design notes the LLM Engineer followed (from PLAN §13.A3, decision (a)):
- **The LLM cannot know whether a trade will succeed before it writes
  `message`.** The system prompt forbids the model from claiming a trade
  is *done* in `message` itself ("I'll buy..." not "I bought..."); the
  *actual* outcome is reported in the separate `trades_executed` /
  `trades_failed` blocks, which the frontend renders as inline
  confirmation/error chips distinct from the prose. No second LLM call to
  "fix" the message after execution — one call, structured execution
  results alongside it.
- **Reuses this file's validated paths, doesn't reimplement them.** Each
  trade in `trades` from the structured LLM output goes through the exact
  same checks as `POST /api/portfolio/trade` in this document (ticker
  format, positive finite quantity, price-cache presence,
  `app.db.execute_trade`, watchlist auto-add, tracked-ticker sync, and an
  immediate snapshot) via the same Python functions
  (`app.portfolio.sync_tracked_tickers`, `app.portfolio.snapshot_once`,
  `app.db.execute_trade`, `app.db.add_to_watchlist`) rather than
  duplicating the logic. Same for `watchlist_changes` against
  `app.db.add_to_watchlist` / `remove_from_watchlist`.
- Persists the user message unconditionally (except on `503`), and the
  assistant message only on a `200` (i.e. only when a real response was
  produced and processed), via `app.db.add_chat_message` (`actions` =
  `json.dumps(...)` of whatever subset of
  `trades_executed`/`trades_failed`/`watchlist_changes` actually ran, or
  `None` if nothing did; always `None` for the user's own message).
- Returns the post-execution `portfolio`/`watchlist` per C2, exactly like
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
