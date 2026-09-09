# FinAlly — LLM Chat Design

Status: **design, implementing against it now**. This is the contract the
Frontend Engineer renders against for the chat panel's action blocks, and
the Integration Tester scripts E2E flows against (mock catalogue below).
Target endpoint contract (request/response shape) is frozen in
`planning/API_CONTRACT.md`'s `POST /api/chat` section — this document
covers what's underneath it: the system prompt, the structured-output
schema, context/history budget, mock response catalogue, and error
handling for the unconfigured/failure cases API_CONTRACT.md left to this
component.

Implementation: `backend/app/llm/`. Handler: `backend/app/api/chat.py`.
Tests: `backend/tests/llm/`, `backend/tests/api/test_chat.py`.

## 1. Structured output schema (what the model returns)

Pydantic models (`app/llm/schema.py`), used as `response_format` in the
real LiteLLM call and as the target of both parse paths (real + mock):

```python
class LLMTrade(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float

class LLMWatchlistChange(BaseModel):
    ticker: str
    action: Literal["add", "remove"]

class LLMChatResponse(BaseModel):
    message: str
    trades: list[LLMTrade] = []
    watchlist_changes: list[LLMWatchlistChange] = []
```

This is exactly PLAN §9's schema. `LLMChatResponse` is *not* the API
response — it's the model's raw structured output before execution. The
API response (`trades_executed`/`trades_failed`/`watchlist_changes` with
`status`/`error`) is built by the executor from this after running each
action through the real validated paths.

## 2. A3 — the message/execution split

The model writes `message` before anything executes, so it can never
truthfully report an outcome. Two things enforce this:

1. **System prompt wording** (`app/llm/prompts.py`): explicitly forbids
   completion language ("bought", "sold", "added", "removed", "done",
   "executed") and requires intent language ("I'll buy...", "I'll add...
   to your watchlist"). The prompt states directly that the actual outcome
   is shown to the user separately and the model must not guess it.
2. **Separate response blocks**: `trades_executed`, `trades_failed`, and
   `watchlist_changes` (with per-item `status`/`error`) are computed by
   `app/llm/executor.py` *after* parsing, from real execution results —
   never from anything the model claims. The frontend renders these as
   distinct chips from the prose, per API_CONTRACT.md.

One LLM call per `/api/chat` request. No reconciliation call.

## 3. Reuse — trades and watchlist changes go through the same paths as manual actions

`app/llm/executor.py` does not reimplement trade or watchlist validation.
For each `LLMTrade`:

1. `app.api.errors.normalize_ticker` — same format gate as
   `POST /api/portfolio/trade` (400-shaped errors caught and turned into a
   `trades_failed` entry instead of propagating).
2. Reject non-finite/non-positive `quantity` with the same message text
   `POST /api/portfolio/trade` uses (B4) — `app/db` doesn't see the price
   cache or this quantity gate belongs to the API layer, and the chat
   handler is a second API-layer caller of the same rule.
3. `price_cache.get_price(ticker)` — reject with the same "No live price
   available..." message as the manual endpoint if `None` (B4).
4. `app.db.execute_trade(...)` — the actual validated write (cash check,
   share check, `InvalidTradeError`/`InsufficientCashError`/
   `InsufficientSharesError` all caught here and surfaced as
   `trades_failed[].error`, never raised past the handler).
5. On success: `app.db.add_to_watchlist(ticker)` (auto-add, same as B4),
   append to `trades_executed`.

After all trades/watchlist changes are processed: `sync_tracked_tickers`
runs once (not per-action) if anything changed, and `snapshot_once` runs
once if at least one trade executed — mirroring
`POST /api/portfolio/trade`'s side effects (§7, A4).

For each `LLMWatchlistChange`: same `normalize_ticker` gate, then
`app.db.add_to_watchlist` / `remove_from_watchlist` directly.
`remove_from_watchlist` returning `False` (ticker wasn't on the list) is
reported as `{"status": "failed", "error": "{TICKER} is not on the
watchlist"}` inside the single `watchlist_changes` array (API_CONTRACT.md
doesn't split this one into two arrays the way trades are split).

## 4. Context and history budget (B10)

- **Portfolio context** (`app/llm/context.py`): cash balance, total value,
  every position with quantity/avg cost/current price/unrealized P&L, and
  every watchlist ticker with its current price — rebuilt fresh on every
  request and injected into the system prompt as plain text. This is
  richer than the `GET /api/watchlist` REST shape (which omits price per
  C3) because it's prompt content, never a response body the frontend
  reads.
- **History bound**: exactly **20 messages** (`app.db.get_chat_history`'s
  own default, reused as-is — no second constant). Loaded *before* the new
  user message is persisted, so the prompt is `[system] + [last 20 stored
  turns] + [new user message]` with no duplication.
- **Action results are NOT included in history fed back to the model.**
  Only `ChatMessage.content` (the plain text) is replayed as prior
  `user`/`assistant` turns — never `ChatMessage.actions`. Rationale: the
  portfolio context is rebuilt fresh every turn (so the model always sees
  current positions/cash regardless of what happened in prior turns), and
  echoing raw action JSON back as conversation turns would both bloat the
  context window and risk the model treating its own past `trades_failed`
  JSON as something to parrot back verbatim. `actions` is still persisted
  to the DB and returned by `GET /api/chat/history` for the frontend to
  render — just not replayed into the LLM's own message list.

## 5. Unconfigured / failure handling (B11)

Two distinct failure modes, both surfaced as **non-2xx** responses in
C5's uniform `{"detail": "..."}` shape — a 200 carrying synthetic
assistant prose would be indistinguishable, to the frontend and the user,
from the model genuinely replying, and would falsely suggest "the AI
responded but is being evasive" rather than "the request failed":

- **Not configured at all** (`OPENROUTER_API_KEY` unset/blank AND
  `LLM_MOCK` is not `"true"`): `POST /api/chat` returns
  `503 {"detail": "The AI assistant is not configured: OPENROUTER_API_KEY
  is missing. Set it in the project .env (or set LLM_MOCK=true for
  testing) and restart."}`. Nothing is persisted to `chat_messages` in
  this path (the user's message never entered the model's context and
  there's nothing to reply to). Checked fresh on every request (not cached
  at import time), so flipping the env var and restarting is enough — no
  code change needed. A startup-time warning is also logged once
  (`app/llm/config.py`, evaluated at module import, i.e. process start)
  so this is visible in the container logs before the first chat attempt:
  `"OPENROUTER_API_KEY is not set; POST /api/chat will return a 503 until
  it is configured (or set LLM_MOCK=true for testing)."` Everything else
  (`/api/portfolio`, `/api/watchlist`, `/api/stream/prices`, etc.) is
  untouched by this — the rest of the app boots and streams normally.
- **Upstream/transient failure** (the real LiteLLM call raises — network
  error, timeout, non-2xx from OpenRouter/Cerebras, insufficient credits)
  **or parse failure** (the model's content isn't recoverable JSON, see
  §6): `POST /api/chat` returns `502 {"detail": "The AI assistant failed
  to produce a response. Please try again in a moment."}`. The user's
  message *is* persisted (it's the user's own words; there's no reason to
  lose it) but **no assistant turn is written** — a fabricated apology
  persisted as an `assistant` message would re-enter the last-20-message
  history on the *next* call (§4) and the model would see itself
  apologizing for something it never said. The frontend renders this
  exactly like any other 4xx/5xx (C5) — one error path, not a fake chat
  bubble.

## 6. Malformed/adversarial output handling (parser)

`app/llm/parser.py`'s `parse_llm_response(raw: str) -> LLMChatResponse`
never raises in a way that reaches the route handler as an unhandled
exception; it either returns a valid `LLMChatResponse` or raises the local
`LLMParseError`, which the handler always catches and converts to the §5
`502` response.

Order of operations:
1. Strip a wrapping ```` ```json ... ``` ```` / ```` ``` ... ``` ```` code
   fence if present (models sometimes wrap structured output in one
   despite instructions not to).
2. Try a **strict** parse (`LLMChatResponse.model_validate_json`) — every
   trade/watchlist entry must fully validate (right types, `side`/`action`
   in their literal sets).
3. If strict parsing fails (bad JSON syntax, wrong top-level type, an
   invalid entry anywhere in `trades`/`watchlist_changes`, a missing/non-
   string `message`), fall back to a **lenient salvage**: `json.loads` the
   cleaned text and, if it's a JSON object with a non-empty string
   `message` field, return `LLMChatResponse(message=..., trades=[],
   watchlist_changes=[])` — i.e. keep the model's conversational reply but
   drop every action rather than executing anything built from a
   partially-malformed payload. This matters concretely: a model that
   returns a fine `message` but botches one trade's `side` value should
   not lose its whole reply, and must never have that trade auto-executed
   from an unvalidated shape either.
4. Only raise `LLMParseError` when nothing usable survives even the
   salvage attempt (not valid JSON at all, JSON that isn't an object, or
   an object with no usable `message` string).

Tested against (see `tests/llm/test_parser.py`): empty string, plain
non-JSON prose, truncated/incomplete JSON, a JSON array instead of an
object, `trades` as a non-list, a trade with `side: "hold"` (not in the
literal set), a trade with a string `quantity` ("ten"), `message` as a
number instead of a string, extra unknown top-level keys (ignored, not an
error), a fenced ` ```json ... ``` ` wrapper around otherwise-valid JSON,
and a message containing embedded quotes/newlines/unicode.

## 7. Mock mode (`LLM_MOCK=true`) — response catalogue

No network call. `app/llm/mock.py` builds the *same* `LLMChatResponse`
shape a real call would produce (then runs it through the identical
executor path), from simple deterministic keyword rules over the raw
user message. This is intentionally simple pattern-matching, not NLU —
documented here as the exact grammar so the Integration Tester can rely on
literal trigger phrases rather than guessing at coverage.

Checked in this order (first match wins):

1. **Trade**: `\b(buy|sell)\b` followed optionally by a number
   (`quantity`, default `1` if omitted) and optionally by
   `shares (of)?`, then a ticker-shaped word. Examples:
   - `"Buy 10 shares of AAPL"` → `trades: [{"ticker": "AAPL", "side":
     "buy", "quantity": 10}]`, message `"I'll buy 10 AAPL."`
   - `"Sell 5 TSLA"` → sell 5 TSLA.
   - `"Buy 100000 AAPL"` → same shape, but with only $10,000 starting cash
     this is the deterministic **failed-trade** path: the executor's real
     `InsufficientCashError` check rejects it, so the response's
     `trades_failed` (not `trades_executed`) carries this one, with
     `error: "Insufficient cash: required ..., available ..."`. Whether a
     trade succeeds or fails is decided by real execution against the
     real DB/price-cache state, not by the mock — so both the success and
     failure paths exercise the exact same executor code a real model
     response would.
   - A trade against a ticker with no cached price (e.g. `"Buy 10 ZZZZ"`
     when `ZZZZ` was never added/priced) is also a genuine
     `trades_failed` case via the real "no live price yet" check.
2. **Watchlist change**: message contains `watchlist`, plus `add` (→
   `action: "add"`) or `remove`/`delete`/`drop` (→ `action: "remove"`);
   the ticker is the first non-stopword alphabetic token in the message.
   Examples:
   - `"Add PYPL to my watchlist"` → add PYPL.
   - `"Remove NFLX from the watchlist"` → remove NFLX. If NFLX isn't
     actually on the watchlist, this is the deterministic
     **failed-watchlist-change** case (`status: "failed"`, `error: "NFLX
     is not on the watchlist"`), again via real execution, not a special
     mock branch.
3. **Plain chat** (no trade/watchlist keywords recognized): a canned but
   context-derived reply — `"You have $X in cash and N open position(s),
   for a total portfolio value of $Y."` — deterministic for a given DB
   state, no trades/watchlist changes.

Known, documented mock limitations (not bugs): quantity-less phrasing
without a clear ticker immediately after the verb (e.g. `"sell all my
TSLA"`) falls through to the plain-chat branch rather than guessing — use
`"sell 5 TSLA"`-style phrasing in E2E scripts. Only one action per message
is extracted (first trade match, or first watchlist match if no trade
matched) — the mock does not batch multiple actions in one turn.

## 8. Model call (real mode)

Per the `cerebras` skill: `openrouter/openai/gpt-oss-120b` via LiteLLM,
Cerebras pinned as the inference provider, `reasoning_effort="low"` (fast,
sufficient for this task), `response_format=LLMChatResponse` for
structured output. `OPENROUTER_API_KEY` is read from the process
environment (loaded from the root `.env` by whatever launches the process
— this component doesn't do its own dotenv loading, consistent with the
rest of the backend).

## 9. Endpoint response assembly (`app/api/chat.py`)

```
POST /api/chat
  -> 503 immediately if unconfigured (§5), nothing persisted
  -> load last-20 history, build portfolio context
  -> persist user message (always, from here on)
  -> mock: build_mock_raw_response(...)
     | real: call_llm(...) -> 502 on LLMCallError (§5), no assistant turn persisted
  -> parse_llm_response(...) -> 502 on LLMParseError (§5/§6), no assistant turn persisted
  -> LLMChatResponse
  -> executor.execute_trades(...), executor.execute_watchlist_changes(...)
  -> sync_tracked_tickers once if anything changed; snapshot_once once if any trade executed
  -> persist assistant message (content=message, actions=json.dumps(...) of whatever ran, or null if nothing ran)
  -> return 200 {message, trades_executed, trades_failed, watchlist_changes,
                 portfolio: <exact GET /api/portfolio response>,
                 watchlist: <bare array of {ticker, added_at}, matching
                             POST /api/portfolio/reset's watchlist field>}
```

This matches `planning/API_CONTRACT.md`'s response contract, including
the two corrections made there after this design doc's first draft: the
`watchlist` field's literal (unwrapped) shape, and the `502`/`503` error
statuses for the upstream/unconfigured cases (previously under-specified
here as a `200` fallback — see §5).
