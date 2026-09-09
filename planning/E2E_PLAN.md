# FinAlly — E2E Test Plan

Status: **plan, published before the suite is finished** (per the working
agreement — the other engineers are already done, but this is the
convention this project follows regardless of order). Written against
`planning/API_CONTRACT.md`, `planning/LLM_DESIGN.md` §7 (mock trigger
grammar), and `planning/FRONTEND_SUMMARY.md` (selectors/testids). Covers
PLAN §12's scenarios plus the two regression assertions the coordinator
requested for the `StaticFiles(html=True)` fix (commit `d18b778`).

Owner: Integration Tester. Scope: `test/` only — Playwright specs,
`docker-compose.test.yml`, fixtures. No application code is touched;
every defect found here is reported, not fixed.

## 1. Infrastructure

`test/docker-compose.test.yml` defines two services, isolated from the
demo container the user is running (`finally` / `finally-data` on host
port 8000 — never touched, never referenced):

- **`app`**: builds the real root `Dockerfile` fresh from the current
  source tree on every run (`context: ..`), tagged locally as
  `finally-e2e:latest` — never reuses a cached/pulled image, so a stale
  image can't hide a regression. `LLM_MOCK=true` always. `/app/db` is
  **tmpfs** (in-memory, wiped on every `docker compose up`), which is the
  primary state-isolation mechanism (see §2). Host port mapped to
  **8100** (not 8000) purely for local debugging convenience; the
  Playwright container talks to it over the compose network as
  `http://app:8000`, not through the host mapping. Own container/volume
  names (`finally-e2e-app`), no `finally-data` volume involved.
- **`playwright`**: the official `mcr.microsoft.com/playwright` image
  (Node + browsers prebuilt, matching the `@playwright/test` version
  pinned in `test/package.json`), bind-mounts `test/` as `/work`, runs
  `npm ci && npx playwright test`. Depends on `app`'s healthcheck
  (`/api/health`), not a sleep. This keeps Playwright's browser
  dependencies out of the production image, per the non-negotiable.

## 2. State isolation

Two layers, both real, chosen together rather than either alone:

1. **tmpfs volume** for `/app/db` — every `docker compose -f
   docker-compose.test.yml up` starts from zero. This is what "fresh
   $10k/10-ticker database" means for a whole suite run.
2. **`POST /api/portfolio/reset` in a `beforeEach`**, via Playwright's
   `request` fixture (no browser navigation needed — fast) — every
   individual test starts clean without needing a container restart
   between tests. This is what makes tests independent of execution
   order and safe to re-run against an already-running compose stack.

Tests run with a single worker (`workers: 1`, `fullyParallel: false`) —
the backend is single-user (hardcoded `user_id="default"`), so two tests
racing the same portfolio would be a self-inflicted flake, not a real
bug. This is a deliberate scope choice: it makes the suite slower but
removes an entire class of false failures. The one exception is the
concurrency spec (§3.8), which *deliberately* issues concurrent requests
from a single test — that's testing the backend's real concurrency
handling, not fighting the suite's own parallelism.

## 3. Scenarios and specs

| Spec file | PLAN §12 scenario | Mechanism |
|---|---|---|
| `fresh-start.spec.ts` | Fresh start: default watchlist, $10k, prices streaming | reset, load, assert 10 rows + `$10,000.00` + connection dot reaches `connected` + at least one price renders |
| `watchlist.spec.ts` | Add/remove a ticker | UI add/remove, plus duplicate-add idempotency and invalid-format rejection |
| `trade.spec.ts` | Buy/sell: cash down/up, position appears/updates/disappears | UI trade bar, both directions, full close removes the position row |
| `api-trade-validation.spec.ts` | (extra rigor, per coordinator's flagged risk area) | Direct API calls: zero/negative quantity, invalid ticker format, unknown-ticker-no-price, insufficient cash, insufficient shares, bad `side`, missing field, watchlist duplicate/invalid/404-remove |
| `concurrency.spec.ts` | (extra rigor: concurrent trade + snapshot writes) | `Promise.all` of N concurrent buys against the same ticker; assert the final position quantity and cash reflect all N fills, not a lost update |
| `portfolio-viz.spec.ts` | Heatmap + P&L chart rendering | Buy a position, assert `heatmap` testid renders (not `heatmap-empty`) and `pnl-chart` renders (not `pnl-empty`) after the trade's immediate snapshot |
| `chat.spec.ts` | AI chat with a mocked trade | Literal mock trigger phrases from `LLM_DESIGN.md` §7: a successful trade, a deterministic insufficient-cash failure, a watchlist add, and a plain-chat reply — asserting the distinct prose/chip rendering |
| `sse-reconnect.spec.ts` | SSE reconnection | `context.setOffline(true/false)` around an already-`connected` stream; assert the dot goes to `reconnecting` (yellow) then back to `connected` (green) — no sleeps |
| `static-fallback.spec.ts` | Regression: `d18b778` (`StaticFiles(html=True)`) | `GET /api/does-not-exist` → JSON `{"detail": ...}`, not HTML; `GET /deep/spa/route` → `index.html` at 200, not `404.html` |

## 4. Mock LLM trigger phrases (verbatim, from LLM_DESIGN.md §7)

Used exactly as documented — not invented — because the mock is
deterministic pattern-matching, not NLU:

- `"Buy 10 shares of AAPL"` → successful trade (AAPL is seeded, $10k
  covers 10 shares at any realistic simulator price).
- `"Buy 100000 AAPL"` → deterministic `trades_failed` (insufficient
  cash).
- `"Add PYPL to my watchlist"` → successful watchlist add.
- `"Remove NFLX from the watchlist"` → successful watchlist remove
  (NFLX is a default ticker).
- Anything without a recognized trade/watchlist keyword → canned
  portfolio-summary plain-chat reply, no actions.

## 5. What is deliberately out of scope for E2E

- **Malformed/adversarial LLM JSON parsing** (`app/llm/parser.py`'s
  salvage path) — this needs to feed the parser raw non-JSON text, which
  the mock catalogue can't produce (it always emits valid
  `LLMChatResponse` JSON) and the real LLM is unavailable (no OpenRouter
  credits, `LLM_MOCK=true` mandated). This is a backend-unit-test
  concern (`backend/tests/llm/test_parser.py`, cited in `LLM_DESIGN.md`
  §6) — noted here so it isn't mistaken for an E2E gap.
- Non-finite (`NaN`/`Infinity`) quantity values — JSON has no literal for
  these, so a real HTTP client can't send them; that check is exercised
  at the unit level, not over the wire.
- `scripts/start.ps1`/`stop.ps1` and Windows — no Windows/PowerShell
  available in this environment (already flagged unverified in
  `DEVOPS_SUMMARY.md`).

## 6. Selectors relied on (from reading `frontend/src` directly)

`connection-status` (`data-status` attribute), `header-total-value`,
`header-cash-balance`, `watchlist-row-{TICKER}`, `price-cell`
(`data-flash`), `change-cell`, add-ticker input (`aria-label="Add ticker
to watchlist"`), remove button (`aria-label="Remove {T} from
watchlist"`), `buy-button`/`sell-button`, trade ticker/quantity inputs
(`aria-label="Trade ticker"`/`"Trade quantity"`), `position-row-{T}`,
`positions-table`, `heatmap`/`heatmap-empty`, `pnl-chart`/`pnl-empty`,
`chat-history`, `chat-message` (`data-role`), `chat-send-button`, chat
input (`aria-label="Chat message"`), `trade-chip-success`/`-failed`,
`watchlist-chip-success`/`-failed`, `chat-loading-history`,
`chat-sending-indicator`.

## 7. Reporting

Real pass/fail counts, run against the real containerized stack, will be
published in `planning/E2E_SUMMARY.md` once the suite runs. Any defect
found is reported with a reproduction, expected vs. actual, and the
failing spec — not silently worked around.
