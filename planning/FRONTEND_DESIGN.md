# FinAlly — Frontend Design

Status: implemented. This is the design the frontend was built against —
component tree, state management, and the SSE hook — published per the
working agreement (design doc before build-out). Read `planning/API_CONTRACT.md`
first; this document assumes it.

## Design plan (frontend-design skill pass)

The brief pins the palette exactly (§2), so the design freedom is in type,
layout, and the small deliberate details that make it read as a built
thing rather than a template.

**Color** (see `src/app/globals.css` `:root` / `@theme inline`):
- `--bg-base #0d1117` — page background
- `--bg-panel #1a1a2e` — panel background (the brief's second dark value,
  used specifically for panel chrome so base vs. panel is visually
  distinct, not just one flat dark color)
- `--bg-panel-raised #21213a` — hover/selected row state
- `--border #2a2e42`, `--border-subtle` — hairline dividers, never a
  shadow
- `--accent-yellow #ecad0a`, `--accent-blue #209dd7`, `--accent-purple
  #753991` (submit buttons), plus `--positive #26a65b` / `--negative
  #e5484d` for P&L and price-flash only — kept semantically separate
  from the three brand accents so "green/red = money moved" never
  competes with "yellow = selection" or "purple = this executes a trade"

**Type**: one sans stack for UI chrome and prose, one monospace stack
(`.font-data`) for every number — ticker symbols, prices, quantities,
timestamps in charts. Tabular figures (`font-variant-numeric:
tabular-nums`) so columns of numbers actually align, which is the one
place a terminal legitimately earns a monospace face (not decoration).
Deliberately **no external font loading** (no `next/font/google`): both
faces are system stacks (`-apple-system/Segoe UI/...` and
`ui-monospace/SF Mono/Cascadia Code/JetBrains Mono/...`). This keeps the
build and the running app free of any network dependency, matching the
project's offline-first posture (simulator by default, SQLite, single
container) — and removes one way the Docker build could fail in a
network-restricted environment.

**Layout**: a fixed three-column desktop-first grid, not a responsive
card wall — that's the deliberate choice for "every pixel earns its
place":
```
┌─────────────────────────────────────────────────────────────────┐
│ FIN|ALLY      Total value $10,482.30   Cash $6,200.10   ● ⚫live │
├───────────────┬───────────────────────────────────┬─────────────┤
│ Watchlist     │  Main chart (selected ticker)      │ AI assistant│
│ ticker price  │                                     │ (chat log + │
│ chg% spark    ├──────────────────┬──────────────────┤  input,    │
│ (scrollable)  │  Heatmap         │  Portfolio value  │  docked)   │
│               │  (treemap)       │  (P&L line)        │            │
│               ├──────────────────┴──────────────────┤            │
│               │  Positions table                     │            │
│               ├───────────────────────────────────────┤            │
│               │  Trade bar (ticker, qty, buy/sell)   │            │
└───────────────┴───────────────────────────────────────┴─────────────┘
```
Left-aligned labels, right-aligned numeric columns throughout (a real
financial-terminal convention, not decoration) — see `PositionsTable`,
`WatchlistRow`. Column headers in dense tables use small
uppercase/tracked labels; this is the one place the frontend-design
skill's "avoid ALL-CAPS labels" guidance is deliberately overridden,
because dense tabular column headers in a trading terminal are
functional domain convention, not a decorative eyebrow — the guidance
targets ALL-CAPS used as flourish above headlines, which this UI has
none of.

**Principles**: flat bordered panels, zero shadows, minimal border-radius
(2px, functional softening only); one recurring motif (the blinking `|`
terminal cursor next to the wordmark, reused as the chat's "thinking"
indicator) rather than a different animation per component; motion
restricted to the price-flash fade and the cursor blink, both
`prefers-reduced-motion`-aware.

## Component tree

```
app/layout.tsx                  — html/body shell, imports globals.css, no external fonts
app/page.tsx                    — the whole terminal; owns cross-cutting state, wires hooks to components

components/
  header/Header.tsx             — wordmark, live total value (B6), cash, ConnectionDot, reset button
  common/
    Panel.tsx                   — shared panel chrome (title bar + scrollable body)
    ConnectionDot.tsx           — green/yellow/red status dot + label
    PriceCell.tsx                — flashing, null-safe price display
    ChangeCell.tsx               — "Chg %" column, null-safe, colored by sign
  watchlist/
    Watchlist.tsx                — panel: add-ticker form, header row, row list, empty state
    WatchlistRowContainer.tsx    — wires per-ticker usePriceHistory into the row (keeps the row presentational)
    WatchlistRow.tsx             — ticker, PriceCell, ChangeCell, Sparkline, remove button
    Sparkline.tsx                — small fixed-size recharts LineChart (no ResponsiveContainer -- see Testing)
  chart/
    MainChart.tsx                — recharts AreaChart for the selected ticker, backed by usePriceHistory
  heatmap/
    PortfolioHeatmap.tsx         — recharts Treemap, sized by market_value, colored by unrealized_pnl_percent
  pnl/
    PnlChart.tsx                 — recharts AreaChart of portfolio_snapshots via usePortfolioHistory
  positions/
    PositionsTable.tsx           — ticker/qty/avg cost/price/P&L/P&L% table, null-safe
  tradebar/
    TradeBar.tsx                 — ticker + qty inputs, Buy/Sell buttons (purple, per the submit-button spec), inline feedback
  chat/
    ChatPanel.tsx                — scrollable history + input, loading/sending states
    ChatMessageBubble.tsx        — one message; user vs. assistant vs. error styling
    ActionChips.tsx              — trades_executed/trades_failed/watchlist_changes as distinct chips from the prose (§13.A3)

hooks/
  usePriceStream.ts              — the one EventSource connection; parses the map payload; flash + connection-status state
  usePriceHistory.ts             — seeds from GET /api/history/{ticker}, then appends live SSE ticks (§13.B13/C4)
  usePortfolio.ts                — GET /api/portfolio, trade(), reset() -- consumes C2 response bodies directly
  useWatchlist.ts                — GET/POST/DELETE /api/watchlist -- no price fields (C3)
  useChat.ts                     — GET /api/chat/history, send() against POST /api/chat
  usePortfolioHistory.ts         — GET /api/portfolio/history, polled + force-refreshable after a trade

lib/
  types.ts                       — every shape mirrors API_CONTRACT.md exactly; ApiError for the one error shape (C5)
  api.ts                         — fetch wrapper; throws ApiError with the parsed `detail` string
  portfolio.ts                   — computeLiveTotalValue() -- the B6 formula, client-side, reading the live SSE map
  format.ts                      — currency/percent/quantity/time formatting; NULL_PLACEHOLDER ("—") for null fields
  constants.ts                   — color tokens (mirrored for recharts, which can't read CSS vars), default tickers, buffer sizes
```

## State management

No global store (Redux/Zustand) — the app is one page, and each concern
maps to exactly one hook with a narrow, typed return value:

- `page.tsx` is the composition root. It calls each hook once and passes
  data + callbacks down as props — no context providers, since nothing
  here is deep enough to need one (three levels at most: page → panel →
  row).
- **Price data** (`usePriceStream`) is the one piece of truly global,
  high-frequency state. Every consumer that needs live prices (Header,
  Watchlist rows, MainChart, TradeBar feedback) reads the same `prices`
  map from the single hook call in `page.tsx`, passed down — there is
  exactly one `EventSource` for the whole app.
- **Portfolio** (`usePortfolio`) and **watchlist** (`useWatchlist`) own
  their own REST-backed state and expose mutators (`trade`, `add`,
  `remove`, `reset`) that update local state directly from the response
  body (C2) — no endpoint in this app is ever re-`GET`-ed after a mutation.
- **Chat** (`useChat`) takes an `onApplied(portfolio, watchlist)` callback
  so that a trade the LLM executes updates the *same* portfolio/watchlist
  state the rest of the UI reads, instead of the chat panel keeping a
  second, divergent copy.
- **Selected ticker** is a single `useState` in `page.tsx` (falls back to
  the first watchlist entry when nothing is explicitly selected yet).
- **`tradeVersion`** is a plain incrementing counter passed to
  `usePortfolioHistory` as `refreshToken`, so the P&L chart refetches
  immediately after any trade (chat-triggered or manual) instead of
  waiting for its 30s poll — matching the backend's "snapshot recorded
  immediately after each trade" behavior.

## The SSE hook (`usePriceStream`)

The one place that owns `EventSource` and the one place that parses the
wire format. Per §13.A2, each `message` event's `data` is a JSON object
keyed by ticker (`{"AAPL": {...}, "GOOGL": {...}}`), not one event per
ticker — the hook `JSON.parse`s the whole frame and diffs it against the
previous frame to derive two independent things from two independent
fields:

1. **Flash direction**, from tick-over-tick `price` (never `day_change`):
   comparing this frame's `price` to the previous frame's `price` per
   ticker. A change sets `flashes[ticker]` to `"up"`/`"down"` and starts a
   500ms timer (`FLASH_DURATION_MS`) that clears it back to `null` — the
   CSS transition on `.price-flash-up`/`.price-flash-down` does the
   actual fade.
2. **Connection status**: `"connecting"` until the first `onopen`, then
   `"connected"`; `onerror` while previously connected means
   `"reconnecting"` (native `EventSource` retry per PLAN §6's `retry:
   1000` directive is already in flight); `readyState === CLOSED` (the
   browser giving up outright) means `"disconnected"`.

Everything downstream (Header, Watchlist, MainChart, TradeBar) reads
`day_change_percent` for the displayed "Chg %" column and `price` for
display value — never mixes the two purposes.

Labeling note carried from the coordinator: `day_change`/`day_change_percent`
are measured against a per-ticker open price captured at first tick
*this server process*, not a real previous trading-day close (the
simulator has no such concept). The UI labels this column "Chg %", not
"1D %" or "Today", so it doesn't overpromise a real trading-day move.

## Price history (§13.B13/C4)

`usePriceHistory(ticker, prices, limit)` is used by both `MainChart` and
every `WatchlistRowContainer` (one call per visible ticker) and is the
single history mechanism for both:

1. On mount / ticker change, it seeds from `GET
   /api/history/{ticker}?limit=N` — the server's bounded ring buffer.
   This is what makes both the sparklines and the main chart survive a
   page refresh, per C4.
2. It then appends live ticks read from the same `prices` map
   `usePriceStream` already maintains (no extra polling — the SSE
   connection is already open), deduping on the tick's timestamp and
   capping the buffer at `limit` (600 for the main chart, ~5 min; 120 for
   sparklines, ~1 min — enough signal at that pixel size without keeping
   ten full 5-minute buffers refreshed on every 500ms frame).

An unknown/brand-new ticker's `points: []` response renders as an empty
chart/`· · ·` sparkline placeholder, not an error state.

## The null-price contract (B6)

`current_price`/`market_value`/`unrealized_pnl`/`unrealized_pnl_percent`
are `null` together for a position with no cached price yet. Every
renderer of these fields (`PriceCell`, `ChangeCell`, `PositionsTable`,
`PortfolioHeatmap`'s color function) treats `null` as its own case,
rendering `NULL_PLACEHOLDER` ("—") or a neutral gray heatmap cell — never
`$0.00`, which would read as a real, non-zero loss.

## Header total value (B6)

`lib/portfolio.ts`'s `computeLiveTotalValue(portfolio, prices)` mirrors
the backend's `compute_total_value` formula exactly: `cash_balance +
Σ(quantity × current_price)`, excluding any position with no price
anywhere (live map or last-known REST value) from the sum. `page.tsx`
recomputes this on every render, which — because `prices` changes on
every SSE frame — means the header updates at the stream's ~500ms
cadence, while still being defined by the identical formula
`GET /api/portfolio` uses, so the two numbers don't visibly disagree.

## Testing strategy

- **Rendering with mock data**: `PositionsTable`, `Watchlist`,
  `ChatPanel`, `Header` each get a test rendering with representative
  mock props, including the null-price case (§ above) and the empty-list
  case.
- **Price flash**: `usePriceStream` is tested directly through a small
  harness component, using a hand-rolled `MockEventSource` installed as
  `global.EventSource` in `jest.setup.ts` (jsdom has no real SSE client).
  Tests fire `onopen`/`onmessage`/`onerror` by hand and assert the flash
  direction appears on a price change and clears after
  `jest.advanceTimersByTime(500)`.
- **Watchlist CRUD**: `Watchlist.test.tsx` drives the add/remove/select
  flows through `@testing-library/user-event`, asserting the callback
  props are called with the normalized ticker, and that a rejected
  `onAdd` (via `ApiError`, matching the one real error shape) surfaces in
  a `role="alert"` without clearing the input.
- **Chat loading state**: `ChatPanel.test.tsx` checks the history-loading
  indicator, the sending ("Thinking…") indicator with the input disabled,
  and that both are absent once idle; a separate case asserts a failed
  trade chip is visually and textually unmistakable (§13.A3).
- **Sparkline** deliberately renders its recharts `LineChart` at a fixed
  pixel size rather than through `ResponsiveContainer`, since jsdom has
  no `ResizeObserver` — this was a real test failure caught and fixed
  during the build, not a hypothetical; see FRONTEND_SUMMARY.md.

## Known trade-off carried into FRONTEND_SUMMARY.md

`next build`'s default Turbopack production build panics in this
environment (`creating new process / binding to a port / Operation not
permitted`) — reproduced with the sandbox both on and off, so it isn't a
harness artifact. The build script pins `next build --webpack`, which
builds and exports cleanly. Flagged for the DevOps Engineer since it
affects the Dockerfile's build command.
