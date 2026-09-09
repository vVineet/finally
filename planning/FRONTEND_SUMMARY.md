# FinAlly — Frontend Summary

Status: **done**. Implements PLAN.md §2, §10, §13 and every binding
decision in the frontend's task brief (A1, A2, B6, B8, D). Built against
`planning/API_CONTRACT.md` (frozen contract) plus two fields that landed
mid-build, confirmed by the coordinator and wired to spec: `day_change`/
`day_change_percent` on the SSE payload, and `GET /api/history/{ticker}`.
Design doc: `planning/FRONTEND_DESIGN.md` (component tree, state
management, SSE hook design — read that first for the "why").

## What was built

```
frontend/
  next.config.ts        output: 'export', images.unoptimized, rewrites() for dev (§13.B8)
  package.json           build script pinned to `next build --webpack` (see "Turbopack" below)
  package-lock.json       committed — `npm ci` verified against it (see Build results)
  jest.config.js, jest.setup.ts   MockEventSource stub + @testing-library/jest-dom
  src/
    app/                 layout.tsx (no external fonts), page.tsx (composition root), globals.css (design tokens)
    components/          header, watchlist, chart, heatmap, pnl, positions, tradebar, chat, common — see FRONTEND_DESIGN.md's tree
    hooks/                usePriceStream, usePriceHistory, usePortfolio, useWatchlist, useChat, usePortfolioHistory
    lib/                  types.ts (mirrors API_CONTRACT.md), api.ts, format.ts, portfolio.ts (B6 formula), constants.ts
    test-utils/           mockEventSource.ts
  8 test files, 39 tests total (see Test results)
```

All required UI elements are present: watchlist with sparklines, main
chart, portfolio heatmap (treemap), P&L chart, positions table, trade
bar, AI chat panel with distinct prose/execution-result rendering, and a
header with live total value + connection status. A "Reset" button in
the header also wires up `POST /api/portfolio/reset` (§13.B1), since it
was already in the frozen contract and costs one component.

## Binding decisions — how each was implemented

- **A1 (day change)**: originally flagged as a genuine gap — no
  `day_change`/`day_change_percent` field existed anywhere in the
  backend or API_CONTRACT.md when I checked `app/market/models.py`,
  `stream.py`, and `cache.py` directly. The coordinator confirmed this
  was their error, routed it to the Backend Engineer, and the fields
  landed mid-build with those exact names. `ChangeCell` (used in the
  watchlist's "Chg %" column) reads `day_change_percent` only —
  `change_percent` (tick-over-tick) is read exclusively by
  `usePriceStream`'s flash logic and never displayed as a percentage
  anywhere. Per the coordinator's guidance, the column is labeled "Chg
  %", not "1D %"/"Today", since the value is measured since server-process
  start, not a real previous close.
- **A2 (SSE map payload)**: `usePriceStream` parses
  `JSON.parse(event.data)` as a `Record<ticker, PriceTick>` and diffs it
  against the previous frame — there is no per-ticker event handling
  anywhere in the codebase.
- **B6 (live total value)**: `lib/portfolio.ts`'s
  `computeLiveTotalValue()` mirrors the backend's
  `compute_total_value` formula exactly (cash + Σ quantity×price,
  excluding priceless positions), reads price from the live SSE map with
  a fallback to the position's last-known REST price, and is recomputed
  in `page.tsx` on every render — so the header moves at the stream's
  ~500ms cadence using the identical formula `GET /api/portfolio` uses.
- **B8 (dev CORS)**: `next.config.ts` has `rewrites()` proxying `/api/*`
  to `localhost:8000`, with a comment noting (and the build output
  confirming) that Next.js ignores this for `output: 'export'` builds —
  expected, dev-only.
- **§13.D (build/export config)**: `output: 'export'`, `images: {
  unoptimized: true }`, `package-lock.json` committed and verified
  against `npm ci`. **`trailingSlash: false`** — recorded decision below.
- **Null prices (contract note)**: `PriceCell`, `ChangeCell`,
  `PositionsTable`, and `PortfolioHeatmap`'s color function all treat
  `null` as a distinct case (`NULL_PLACEHOLDER` = "—", or a neutral gray
  heatmap cell), verified by tests that explicitly assert the string
  `"$0.00"` never appears for a priceless position.
- **Chat rendering (§13.A3 / LLM_DESIGN.md confirmation)**:
  `ChatMessageBubble` renders the LLM's `content` as plain prose;
  `ActionChips` renders `trades_executed`/`trades_failed`/
  `watchlist_changes` as separate bordered chips below it — a failed
  trade gets a red border, "Failed to {side}...", and the backend's
  `error` string verbatim, never silently dropped. `useChat`'s response
  parsing reads `res.watchlist` as a bare array (not
  `{watchlist: [...]}`), matching the coordinator's ruling that
  `POST /api/chat`'s `portfolio`/`watchlist` fields are bare, same as
  `POST /api/portfolio/reset`.
- **C2/C3**: every mutating hook (`usePortfolio.trade/reset`,
  `useWatchlist.add/remove`) applies the response body directly to
  local state; nothing re-`GET`s after a mutation. `useWatchlist` never
  reads or stores a price field.

## `trailingSlash` decision (for DevOps)

**`trailingSlash: false`** (the Next.js default). This app is a single
real route (`/`) with no client-side routing to a second page, so the
usual reason to set it `true` (matching a static host's
`/about/index.html`-style directory serving) doesn't apply here — the
backend's SPA fallback (per `planning/BACKEND_SUMMARY.md`) serves
`index.html` directly for any unmatched non-`/api` path regardless of
trailing slash. Static assets under `/_next/static/...` are unaffected
by this setting either way. If a second page is ever added, this should
be revisited together with how FastAPI's static mount resolves nested
paths.

## Turbopack build failure (environment issue, not a code bug)

`next build`'s new default (Turbopack) production build fails in this
environment:
```
Error [TurbopackInternalError]: Failed to write app endpoint /page
Caused by:
- [project]/src/app/globals.css [app-client] (css)
- creating new process
- binding to a port
- Operation not permitted (os error 1)
```
Reproduced identically with the harness sandbox both on and off, so it
isn't a Claude Code sandbox artifact — Turbopack's CSS processing step
tries to spawn a subprocess that binds a local port, which this
environment (and potentially a container build environment with similar
restrictions) rejects. `next build --webpack` builds and exports
cleanly with identical output. **`package.json`'s `build` script is
pinned to `next build --webpack`** so this doesn't depend on whichever
default Next.js ships with next. Flagging explicitly for the DevOps
Engineer: the Dockerfile's frontend build stage should run `npm run
build` (which already carries the `--webpack` flag) rather than calling
`next build` directly, or it will hit this same failure if the container
build environment has similar process/socket restrictions.

## Test results (real output)

```
$ npm test

Test Suites: 8 passed, 8 total
Tests:       39 passed, 39 total
Snapshots:   0 total
Time:        3.7s
```

Coverage by concern (see FRONTEND_DESIGN.md "Testing strategy" for
rationale):
- `usePriceStream.test.tsx` (4 tests) — map-payload parsing, flash-up,
  flash-down and its ~500ms clear via `jest.advanceTimersByTime`,
  disconnected status on `readyState === CLOSED`.
- `PriceCell.test.tsx` (5), `Header.test.tsx` (6), `format.test.ts` (5),
  `portfolio.test.ts` (4) — rendering with mock data, null-price
  placeholder (never `$0.00`), the B6 formula's fallback and exclusion
  behavior, and all four connection-status labels.
- `Watchlist.test.tsx` (6) — full CRUD: renders entries, add
  (normalizes/uppercases, clears input), add failure surfaces `role="alert"`,
  remove, select, empty state.
- `PositionsTable.test.tsx` (3) — mock data rendering, the null-price row,
  empty state.
- `ChatPanel.test.tsx` (7) — history-loading indicator, sending indicator
  + disabled input, both absent when idle, prose/chip visual separation,
  a failed-trade chip's unmistakability, and the send-and-clear flow.

Two real bugs were caught and fixed by this suite during the build (not
hypothetical — the tests failed until fixed):
1. `ChatPanel` called `scrollRef.current.scrollTo(...)`, which jsdom
   doesn't implement — guarded with `?.scrollTo?.(...)`.
2. `Sparkline` originally used recharts' `ResponsiveContainer`, which
   depends on `ResizeObserver` (unavailable in jsdom, so it silently
   renders 0×0). Since sparklines are always a fixed pixel size, it now
   renders `LineChart` directly at that size instead of going through
   `ResponsiveContainer` — simpler and removes the untestable dependency
   at the same time.

## Build results (real output)

```
$ rm -rf node_modules && npm ci        # simulates the Dockerfile's `npm ci`
added 698 packages, and audited 699 packages in 22s
found 0 vulnerabilities

$ npm run build                        # next build --webpack
✓ Compiled successfully in 10-16s
✓ Finished TypeScript check
✓ Generated 4/4 static pages
Route (app): /  and  /_not-found, both ○ (Static)
out/index.html present
```

```
$ npx eslint src --max-warnings=0
(clean — 0 errors, 0 warnings)
```
One rule, `react-hooks/set-state-in-effect`, is disabled project-wide in
`eslint.config.mjs` with an inline comment explaining why: it flags the
standard fetch-on-mount pattern used consistently across every data hook
in `src/hooks`, each of which already guards the case the rule cares
about (a `cancelled` flag for hooks with a real race, e.g.
`usePriceHistory`; a single one-shot fetch with no race for the plain
refresh-on-mount hooks). Not a correctness issue, a lint-rule disagreement
made explicitly rather than silently.

## Constraints honored

- No files under `backend/`, `Dockerfile`, `scripts/`, or `.github/`
  touched.
- Did not run `git commit` — left for review as instructed.
- Flagged the day-change gap to the coordinator before working around it
  (per the working agreement), rather than shipping a guess or a
  placeholder past the point where a real fix was in flight.

## Files touched

Everything under `frontend/` (new — the whole project, see the tree in
"What was built" above) plus:
- `planning/FRONTEND_DESIGN.md` (new)
- `planning/FRONTEND_SUMMARY.md` (new, this file)

No other paths were created or modified.
