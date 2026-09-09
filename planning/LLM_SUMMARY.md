# FinAlly — LLM Integration Summary

Status: **done**. Implements PLAN.md §9, the frozen `POST /api/chat`
contract in `planning/API_CONTRACT.md`, and the binding decisions A3, B10,
B11, and the `LLM_MOCK` requirement from §13. Design doc (system prompt,
structured output schema, mock catalogue, context/history budget):
`planning/LLM_DESIGN.md` — written first, before implementation, per the
project's handoff convention.

## What was built

```
backend/app/llm/
    __init__.py   Public API surface (import from here, not submodules)
    schema.py     LLMTrade, LLMWatchlistChange, LLMChatResponse (PLAN §9's
                  structured output schema -- the model's raw output, not
                  the API response shape)
    config.py     is_mock_mode(), has_api_key() (re-read env every call,
                  B11); startup warning logged at import time
    context.py    build_portfolio_context() (cash/positions/watchlist +
                  live prices, for the prompt), to_prompt_text()
    prompts.py     SYSTEM_PROMPT (A3 wording), build_messages() (system +
                  last-20 history + new message, B10)
    client.py     call_llm() -- LiteLLM -> OpenRouter -> Cerebras per the
                  cerebras skill; wraps every failure in LLMCallError
    mock.py       build_mock_response()/build_mock_raw_response() -- the
                  LLM_MOCK=true deterministic catalogue (§7 of the design doc)
    parser.py     parse_llm_response() -- strict parse, then a lenient
                  message-only salvage, else LLMParseError; never an
                  unhandled exception (§6)
    executor.py   execute_trades(), execute_watchlist_changes() -- runs
                  each action through app.db.execute_trade /
                  add_to_watchlist / remove_from_watchlist and
                  app.api.errors.normalize_ticker (reused, not
                  reimplemented); partitions into trades_executed/
                  trades_failed/watchlist_changes

backend/app/api/chat.py
    GET /api/chat/history (unchanged) + POST /api/chat (implemented,
    replacing the 501 stub): 503 if unconfigured -> load history -> build
    context -> persist user message -> mock or real call (502 on
    LLMCallError, no assistant turn persisted) -> parse (502 on
    LLMParseError, no assistant turn persisted) -> execute actions ->
    sync_tracked_tickers/snapshot_once once each if anything ran ->
    persist assistant message -> return 200 {message, trades_executed,
    trades_failed, watchlist_changes, portfolio, watchlist}

backend/tests/llm/       64 new tests (parser, mock, executor, context,
                          client, config, prompts)
backend/tests/api/test_chat.py   rewritten: the old 501-stub test is gone
                          (route is implemented now); 15 tests covering
                          mock-mode plain chat/trade success/trade
                          failure/no-price failure/watchlist add/remove
                          (present and absent), the 503 unconfigured path,
                          and the real (non-mock) call path with call_llm
                          monkeypatched (success, LLMCallError -> 502,
                          parse failure -> 502, with a persistence check
                          that no synthetic assistant turn is written) --
                          no network in any test.
```

## Binding decisions — how each was implemented

- **A3**: one LLM call. The model's `message` is written before execution
  and the system prompt explicitly forbids completion language ("bought",
  "added", "done") in favor of intent language ("I'll buy...", "I'll
  add..."), with the reasoning spelled out in the prompt itself (the model
  cannot know the outcome yet). The actual outcome is computed by
  `app/llm/executor.py` from real `app.db`/price-cache execution and
  returned in separate `trades_executed`/`trades_failed`/
  `watchlist_changes` blocks the frontend renders as distinct chips.
  Verified in mock-mode tests (`test_chat_successful_trade_mock_mode`,
  `test_chat_failed_trade_mock_mode`): the assistant's `message` never
  contains "bought", and the failed case's `trades_failed[0].error` is the
  real `InsufficientCashError` text, generated after the message was
  written.
- **Reuse, not reimplementation**: `execute_trades`/
  `execute_watchlist_changes` call `app.api.errors.normalize_ticker`,
  `app.db.execute_trade`, `app.db.add_to_watchlist`,
  `app.db.remove_from_watchlist` directly -- no trade or watchlist
  validation logic is duplicated. The one thing this layer *does* own (per
  the Backend API Engineer's note in `DATABASE_SUMMARY.md`): the
  price-cache lookup and the "no live price yet" rejection, since
  `app.db` never imports `app.market` -- same division of responsibility
  `app/api/portfolio.py`'s trade endpoint uses, same error message text.
- **B10**: history bounded at exactly 20 messages
  (`app.db.get_chat_history`'s own default, reused directly -- no second
  constant to drift). Loaded *before* the new user message is persisted
  (no duplication in the prompt). Action results
  (`trades_executed`/`trades_failed`/`watchlist_changes`) are **not**
  replayed into the model's message history -- only `ChatMessage.content`
  is. Rationale and the one place this is decided:
  `planning/LLM_DESIGN.md` §4.
- **B11**: `POST /api/chat` returns `503 {"detail": "..."}` when
  `OPENROUTER_API_KEY` is unset/blank and `LLM_MOCK` isn't `"true"`,
  checked fresh on every request (not cached at import time). Nothing else
  in the app is touched by this -- verified by the pre-existing
  market/portfolio/watchlist test suites still passing untouched. A
  startup-time warning is logged from `app/llm/config.py` (imported
  transitively at process start via `app.api.chat` -> `app.main`, so no
  edit to `app/main.py` was needed). Separately, a *transient* failure
  (the real call raising, or the response failing to parse) returns `502`
  with C5's uniform `{"detail": ...}` shape rather than a `200` -- the
  user's message is still persisted, but **no assistant turn is
  written**, so a fabricated reply never enters the last-20-message
  context window fed back to the model on the next call. The frontend
  renders it through its single error path, visibly distinct from a real
  reply. Both paths are covered by
  monkeypatched tests (no network).
- **`LLM_MOCK=true`**: `app/llm/mock.py` implements simple, documented
  keyword extraction (see `planning/LLM_DESIGN.md` §7 for the exact
  grammar and canonical trigger phrases) that produces the same
  `LLMChatResponse` shape a real call would, then runs it through the
  *same* executor as a real response. Whether a mock-triggered trade
  succeeds or fails is decided by real execution against real DB/price-
  cache state (e.g. `"Buy 1000000 AAPL"` naturally hits
  `InsufficientCashError`) -- not a special-cased mock branch -- so the
  trade-success, trade-failure, watchlist-success, and watchlist-failure
  paths all exercise the identical code a real model response would.
  Covered end-to-end in `tests/api/test_chat.py` (`client.post` through
  the full FastAPI route) and in isolation in `tests/llm/test_mock.py`.
- **Malformed/adversarial JSON (parser)**: `parse_llm_response` never
  raises anything except the local `LLMParseError`, which the route
  handler always catches. Tested against: empty string, plain prose, a
  JSON array instead of an object, truncated/incomplete JSON, a fenced
  ` ```json ` wrapper, `message` as a non-string, a blank/whitespace-only
  `message`, a `trades` entry with an invalid `side`/`action` literal, a
  string `quantity`, `trades` as a non-list, a 5,000-entry trades array, a
  200-level deeply nested extra field, and a message with embedded
  quotes/newlines/emoji -- 20 tests in `tests/llm/test_parser.py`. The
  general rule: a fully-invalid action list never blocks the model's
  conversational reply from reaching the user (message is salvaged,
  actions are dropped), and nothing survives as a crash.

## A contract ambiguity found and resolved (with the coordinator)

The original `POST /api/chat` target contract used a
`{"...": "same shape as GET /api/watchlist"}` placeholder for the response
body's `watchlist` field. Taken literally that means double-wrapping
(`{"watchlist": {"watchlist": [...]}}`), which contradicts the already-
shipped `POST /api/portfolio/reset`'s precedent of a bare array. Flagged
before implementing either way; the coordinator ruled in favor of the bare
array (matching `reset`, consistent with C2's "one consistent shape for
mutating endpoints" intent). Implemented that way, and
`planning/API_CONTRACT.md`'s chat section was corrected to spell out the
literal shape instead of the ambiguous placeholder (confined to that one
section, not a restructure).

## A real bug found and fixed during implementation

A genuine circular import: `app.llm.executor` importing
`app.api.errors.normalize_ticker` at module level, while `app.api.chat`
(part of the `app.api` package `executor`'s import chain pulls in) imports
`app.llm` at module level. This only manifested when `app.llm` was
imported before `app.api` had a chance to fully initialize (masked when
`app.main`/`app.api` happened to import first, which is what the earlier
`import app.main` sanity check did -- but broke immediately under
`import app.llm` directly, which is exactly the order `tests/llm/`
exercises). Fixed with a deferred (function-body) import of
`normalize_ticker` in `execute_trades`/`execute_watchlist_changes`,
documented inline; still the exact same function, no duplication.

## Test results (real output)

```
$ uv run --extra dev pytest -q
283 passed in 11.39s
```
(208 pre-existing across `tests/db`, `tests/market`, `tests/api`,
`tests/portfolio` -- untouched except the necessary rewrite of
`tests/api/test_chat.py`, whose stub-era 501 test no longer applies.
Net +75 from this stage: 64 in `tests/llm/`, plus `test_chat.py` going
to 15 tests from the 4 it replaced.)

```
$ uv run --extra dev ruff check app/ tests/
All checks passed!
```

Coverage of every file this component owns
(`pytest -q --cov=app --cov-report=term-missing`): **100%** on
`app/api/chat.py` and every file in `app/llm/` (schema, config, context,
prompts, client, mock, parser, executor, `__init__`). Whole-repo total is
97% (1307 statements, 42 missed) -- all remaining gaps are in files this
component doesn't own (pre-existing, documented in `BACKEND_SUMMARY.md`/
`DATABASE_SUMMARY.md`/`MARKET_DATA_SUMMARY.md`).

## Manual real-network smoke test (not part of the pytest suite)

Ran `call_llm` + `parse_llm_response` against the actual
LiteLLM -> OpenRouter -> Cerebras path (no monkeypatching) once, to verify
the integration itself (model name, `response_format`, `extra_body`
provider pinning, auth) is wired correctly end to end. Result: the request
reached OpenRouter and authenticated fine, but the account behind the
root `.env`'s `OPENROUTER_API_KEY` has never purchased credits, so
OpenRouter returned `402 Insufficient credits`. `LLMCallError` caught it
exactly as designed (verified separately from the pytest suite by
inspecting the traceback). This means: nobody will see a genuine
(non-mock) model reply in this environment until that OpenRouter account
has credits -- flagged to the coordinator. `LLM_MOCK=true` (what E2E/CI
actually uses per PLAN §12) is entirely unaffected.

## Constraints honored

- No edits to `backend/app/main.py`, `backend/app/api/history.py`,
  `backend/app/market/cache.py`, `backend/app/db/`, `frontend/`, or
  `Dockerfile`.
- `backend/app/api/chat.py` reuses `app.api.portfolio.build_portfolio_response`
  and `app.api.deps.get_price_cache`/`get_market_source` rather than
  re-deriving portfolio state or price-cache access.
- Did not run `git commit`.

## Files touched

- `backend/app/llm/__init__.py`, `client.py`, `config.py`, `context.py`,
  `executor.py`, `mock.py`, `parser.py`, `prompts.py`, `schema.py` (new)
- `backend/app/api/chat.py` (rewritten: real handler replacing the 501 stub)
- `backend/tests/llm/__init__.py`, `conftest.py`, `test_client.py`,
  `test_config.py`, `test_context.py`, `test_executor.py`, `test_mock.py`,
  `test_parser.py`, `test_prompts.py` (new)
- `backend/tests/api/test_chat.py` (rewritten for the implemented endpoint)
- `backend/pyproject.toml` (added `litellm`, `pydantic` via `uv add`)
- `planning/LLM_DESIGN.md` (new), `planning/LLM_SUMMARY.md` (this file, new)
- `planning/API_CONTRACT.md` (chat section only: replaced the ambiguous
  `{"...": "same shape as X"}` placeholders with the literal response
  shape, per the coordinator's ruling)

No files outside `backend/app/llm/`, `backend/app/api/chat.py`,
`backend/tests/llm/`, `backend/tests/api/test_chat.py`,
`backend/pyproject.toml`, and the three planning docs above were created
or modified.
