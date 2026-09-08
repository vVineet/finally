# FinAlly — AI Trading Workstation

## Project Specification

## 1. Vision

FinAlly (Finance Ally) is a visually stunning AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot.

This is the capstone project for an agentic AI coding course. It is built entirely by Coding Agents demonstrating how orchestrated AI agents can produce a production-quality full-stack application. Agents interact through files in `planning/`.

## 2. User Experience

### First Launch

The user runs a single Docker command (or a provided start script). A browser opens to `http://localhost:8000`. No login, no signup. They immediately see:

- A watchlist of 10 default tickers with live-updating prices in a grid
- $10,000 in virtual cash
- A dark, data-rich trading terminal aesthetic
- An AI chat panel ready to assist

### What the User Can Do

- **Watch prices stream** — prices flash green (uptick) or red (downtick) with subtle CSS animations that fade
- **View sparkline mini-charts** — price action beside each ticker in the watchlist, accumulated on the frontend from the SSE stream since page load (sparklines fill in progressively)
- **Click a ticker** to see a larger detailed chart in the main chart area
- **Buy and sell shares** — market orders only, instant fill at current price, no fees, no confirmation dialog
- **Monitor their portfolio** — a heatmap (treemap) showing positions sized by weight and colored by P&L, plus a P&L chart tracking total portfolio value over time
- **View a positions table** — ticker, quantity, average cost, current price, unrealized P&L, % change
- **Chat with the AI assistant** — ask about their portfolio, get analysis, and have the AI execute trades and manage the watchlist through natural language
- **Manage the watchlist** — add/remove tickers manually or via the AI chat

### Visual Design

- **Dark theme**: backgrounds around `#0d1117` or `#1a1a2e`, muted gray borders, no pure black
- **Price flash animations**: brief green/red background highlight on price change, fading over ~500ms via CSS transitions
- **Connection status indicator**: a small colored dot (green = connected, yellow = reconnecting, red = disconnected) visible in the header
- **Professional, data-dense layout**: inspired by Bloomberg/trading terminals — every pixel earns its place
- **Responsive but desktop-first**: optimized for wide screens, functional on tablet

### Color Scheme
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991` (submit buttons)

## 3. Architecture Overview

### Single Container, Single Port

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

- **Frontend**: Next.js with TypeScript, built as a static export (`output: 'export'`), served by FastAPI as static files
- **Backend**: FastAPI (Python), managed as a `uv` project
- **Database**: SQLite, single file at `db/finally.db`, volume-mounted for persistence
- **Real-time data**: Server-Sent Events (SSE) — simpler than WebSockets, one-way server→client push, works everywhere
- **AI integration**: LiteLLM → OpenRouter (Cerebras for fast inference), with structured outputs for trade execution
- **Market data**: Environment-variable driven — simulator by default, real data via Massive API if key provided

### Why These Choices

| Decision | Rationale |
|---|---|
| SSE over WebSockets | One-way push is all we need; simpler, no bidirectional complexity, universal browser support |
| Static Next.js export | Single origin, no CORS issues, one port, one container, simple deployment |
| SQLite over Postgres | No auth = no multi-user = no need for a database server; self-contained, zero config |
| Single Docker container | Students run one command; no docker-compose for production, no service orchestration |
| uv for Python | Fast, modern Python project management; reproducible lockfile; what students should learn |
| Market orders only | Eliminates order book, limit order logic, partial fills — dramatically simpler portfolio math |

---

## 4. Directory Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project (Python)
│   └── db/                   # Schema definitions, seed data, migration logic
├── planning/                 # Project-wide documentation for agents
│   ├── PLAN.md               # This document
│   └── ...                   # Additional agent reference docs
├── scripts/
│   ├── start_mac.sh          # Launch Docker container (macOS/Linux)
│   ├── stop_mac.sh           # Stop Docker container (macOS/Linux)
│   ├── start_windows.ps1     # Launch Docker container (Windows PowerShell)
│   └── stop_windows.ps1      # Stop Docker container (Windows PowerShell)
├── test/                     # Playwright E2E tests + docker-compose.test.yml
├── db/                       # Volume mount target (SQLite file lives here at runtime)
│   └── .gitkeep              # Directory exists in repo; finally.db is gitignored
├── Dockerfile                # Multi-stage build (Node → Python)
├── docker-compose.yml        # Optional convenience wrapper
├── .env                      # Environment variables (gitignored, .env.example committed)
└── .gitignore
```

### Key Boundaries

- **`frontend/`** is a self-contained Next.js project. It knows nothing about Python. It talks to the backend via `/api/*` endpoints and `/api/stream/*` SSE endpoints. Internal structure is up to the Frontend Engineer agent.
- **`backend/`** is a self-contained uv project with its own `pyproject.toml`. It owns all server logic including database initialization, schema, seed data, API routes, SSE streaming, market data, and LLM integration. Internal structure is up to the Backend/Market Data agents.
- **`backend/db/`** contains schema SQL definitions and seed logic. The backend lazily initializes the database on first request — creating tables and seeding default data if the SQLite file doesn't exist or is empty.
- **`db/`** at the top level is the runtime volume mount point. The SQLite file (`db/finally.db`) is created here by the backend and persists across container restarts via Docker volume.
- **`planning/`** contains project-wide documentation, including this plan. All agents reference files here as the shared contract.
- **`test/`** contains Playwright E2E tests and supporting infrastructure (e.g., `docker-compose.test.yml`). Unit tests live within `frontend/` and `backend/` respectively, following each framework's conventions.
- **`scripts/`** contains start/stop scripts that wrap Docker commands.

---

## 5. Environment Variables

```bash
# Required: OpenRouter API key for LLM chat functionality
OPENROUTER_API_KEY=your-openrouter-api-key-here

# Optional: Massive (Polygon.io) API key for real market data
# If not set, the built-in market simulator is used (recommended for most users)
MASSIVE_API_KEY=

# Optional: Set to "true" for deterministic mock LLM responses (testing)
LLM_MOCK=false
```

### Behavior

- If `MASSIVE_API_KEY` is set and non-empty → backend uses Massive REST API for market data
- If `MASSIVE_API_KEY` is absent or empty → backend uses the built-in market simulator
- If `LLM_MOCK=true` → backend returns deterministic mock LLM responses (for E2E tests)
- The backend reads `.env` from the project root (mounted into the container or read via docker `--env-file`)

---

## 6. Market Data

### Two Implementations, One Interface

Both the simulator and the Massive client implement the same abstract interface. The backend selects which to use based on the environment variable. All downstream code (SSE streaming, price cache, frontend) is agnostic to the source.

### Simulator (Default)

- Generates prices using geometric Brownian motion (GBM) with configurable drift and volatility per ticker
- Updates at ~500ms intervals
- Correlated moves across tickers (e.g., tech stocks move together)
- Occasional random "events" — sudden 2-5% moves on a ticker for drama
- Starts from realistic seed prices (e.g., AAPL ~$190, GOOGL ~$175, etc.)
- Runs as an in-process background task — no external dependencies

### Massive API (Optional)

- REST API polling (not WebSocket) — simpler, works on all tiers
- Polls for the union of all watched tickers on a configurable interval
- Free tier (5 calls/min): poll every 15 seconds
- Paid tiers: poll every 2-15 seconds depending on tier
- Parses REST response into the same format as the simulator

### Shared Price Cache

- A single background task (simulator or Massive poller) writes to an in-memory price cache
- The cache holds the latest price, previous price, and timestamp for each ticker
- SSE streams read from this cache and push updates to connected clients
- This architecture supports future multi-user scenarios without changes to the data layer

### SSE Streaming

- Endpoint: `GET /api/stream/prices`
- Long-lived SSE connection; client uses native `EventSource` API
- Server pushes price updates for all tickers known to the system at a regular cadence (~500ms) — in the single-user model this is equivalent to the user's watchlist
- Each SSE event contains ticker, price, previous price, timestamp, and change direction
- Client handles reconnection automatically (EventSource has built-in retry)

---

## 7. Database

### SQLite with Lazy Initialization

The backend checks for the SQLite database on startup (or first request). If the file doesn't exist or tables are missing, it creates the schema and seeds default data. This means:

- No separate migration step
- No manual database setup
- Fresh Docker volumes start with a clean, seeded database automatically

### Schema

All tables include a `user_id` column defaulting to `"default"`. This is hardcoded for now (single-user) but enables future multi-user support without schema migration.

**users_profile** — User state (cash balance)
- `id` TEXT PRIMARY KEY (default: `"default"`)
- `cash_balance` REAL (default: `10000.0`)
- `created_at` TEXT (ISO timestamp)

**watchlist** — Tickers the user is watching
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `added_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**positions** — Current holdings (one row per ticker per user)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `quantity` REAL (fractional shares supported)
- `avg_cost` REAL
- `updated_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**trades** — Trade history (append-only log)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `side` TEXT (`"buy"` or `"sell"`)
- `quantity` REAL (fractional shares supported)
- `price` REAL
- `executed_at` TEXT (ISO timestamp)

**portfolio_snapshots** — Portfolio value over time (for P&L chart). Recorded every 30 seconds by a background task, and immediately after each trade execution.
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `total_value` REAL
- `recorded_at` TEXT (ISO timestamp)

**chat_messages** — Conversation history with LLM
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `role` TEXT (`"user"` or `"assistant"`)
- `content` TEXT
- `actions` TEXT (JSON — trades executed, watchlist changes made; null for user messages)
- `created_at` TEXT (ISO timestamp)

### Default Seed Data

- One user profile: `id="default"`, `cash_balance=10000.0`
- Ten watchlist entries: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

---

## 8. API Endpoints

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE stream of live price updates |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Current positions, cash balance, total value, unrealized P&L |
| POST | `/api/portfolio/trade` | Execute a trade: `{ticker, quantity, side}` |
| GET | `/api/portfolio/history` | Portfolio value snapshots over time (for P&L chart) |

### Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/watchlist` | Current watchlist tickers with latest prices |
| POST | `/api/watchlist` | Add a ticker: `{ticker}` |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message, receive complete JSON response (message + executed actions) |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (for Docker/deployment) |

---

## 9. LLM Integration

When writing code to make calls to LLMs, use cerebras-inference skill to use LiteLLM via OpenRouter to the `openrouter/openai/gpt-oss-120b` model with Cerebras as the inference provider. Structured Outputs should be used to interpret the results.

There is an OPENROUTER_API_KEY in the .env file in the project root.

### How It Works

When the user sends a chat message, the backend:

1. Loads the user's current portfolio context (cash, positions with P&L, watchlist with live prices, total portfolio value)
2. Loads recent conversation history from the `chat_messages` table
3. Constructs a prompt with a system message, portfolio context, conversation history, and the user's new message
4. Calls the LLM via LiteLLM → OpenRouter, requesting structured output, using the cerebras-inference skill
5. Parses the complete structured JSON response
6. Auto-executes any trades or watchlist changes specified in the response
7. Stores the message and executed actions in `chat_messages`
8. Returns the complete JSON response to the frontend (no token-by-token streaming — Cerebras inference is fast enough that a loading indicator is sufficient)

### Structured Output Schema

The LLM is instructed to respond with JSON matching this schema:

```json
{
  "message": "Your conversational response to the user",
  "trades": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10}
  ],
  "watchlist_changes": [
    {"ticker": "PYPL", "action": "add"}
  ]
}
```

- `message` (required): The conversational text shown to the user
- `trades` (optional): Array of trades to auto-execute. Each trade goes through the same validation as manual trades (sufficient cash for buys, sufficient shares for sells)
- `watchlist_changes` (optional): Array of watchlist modifications

### Auto-Execution

Trades specified by the LLM execute automatically — no confirmation dialog. This is a deliberate design choice:
- It's a simulated environment with fake money, so the stakes are zero
- It creates an impressive, fluid demo experience
- It demonstrates agentic AI capabilities — the core theme of the course

If a trade fails validation (e.g., insufficient cash), the error is included in the chat response so the LLM can inform the user.

### System Prompt Guidance

The LLM should be prompted as "FinAlly, an AI trading assistant" with instructions to:
- Analyze portfolio composition, risk concentration, and P&L
- Suggest trades with reasoning
- Execute trades when the user asks or agrees
- Manage the watchlist proactively
- Be concise and data-driven in responses
- Always respond with valid structured JSON

### LLM Mock Mode

When `LLM_MOCK=true`, the backend returns deterministic mock responses instead of calling OpenRouter. This enables:
- Fast, free, reproducible E2E tests
- Development without an API key
- CI/CD pipelines

---

## 10. Frontend Design

### Layout

The frontend is a single-page application with a dense, terminal-inspired layout. The specific component architecture and layout system is up to the Frontend Engineer, but the UI should include these elements:

- **Watchlist panel** — grid/table of watched tickers with: ticker symbol, current price (flashing green/red on change), daily change %, and a sparkline mini-chart (accumulated from SSE since page load)
- **Main chart area** — larger chart for the currently selected ticker, with at minimum price over time. Clicking a ticker in the watchlist selects it here.
- **Portfolio heatmap** — treemap visualization where each rectangle is a position, sized by portfolio weight, colored by P&L (green = profit, red = loss)
- **P&L chart** — line chart showing total portfolio value over time, using data from `portfolio_snapshots`
- **Positions table** — tabular view of all positions: ticker, quantity, avg cost, current price, unrealized P&L, % change
- **Trade bar** — simple input area: ticker field, quantity field, buy button, sell button. Market orders, instant fill.
- **AI chat panel** — docked/collapsible sidebar. Message input, scrolling conversation history, loading indicator while waiting for LLM response. Trade executions and watchlist changes shown inline as confirmations.
- **Header** — portfolio total value (updating live), connection status indicator, cash balance

### Technical Notes

- Use `EventSource` for SSE connection to `/api/stream/prices`
- Canvas-based charting library preferred (Lightweight Charts or Recharts) for performance
- Price flash effect: on receiving a new price, briefly apply a CSS class with background color transition, then remove it
- All API calls go to the same origin (`/api/*`) — no CORS configuration needed
- Tailwind CSS for styling with a custom dark theme

---

## 11. Docker & Deployment

### Multi-Stage Dockerfile

```
Stage 1: Node 20 slim
  - Copy frontend/
  - npm install && npm run build (produces static export)

Stage 2: Python 3.12 slim
  - Install uv
  - Copy backend/
  - uv sync (install Python dependencies from lockfile)
  - Copy frontend build output into a static/ directory
  - Expose port 8000
  - CMD: uvicorn serving FastAPI app
```

FastAPI serves the static frontend files and all API routes on port 8000.

### Docker Volume

The SQLite database persists via a named Docker volume:

```bash
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally
```

The `db/` directory in the project root maps to `/app/db` in the container. The backend writes `finally.db` to this path.

### Start/Stop Scripts

**`scripts/start_mac.sh`** (macOS/Linux):
- Builds the Docker image if not already built (or if `--build` flag passed)
- Runs the container with the volume mount, port mapping, and `.env` file
- Prints the URL to access the app
- Optionally opens the browser

**`scripts/stop_mac.sh`** (macOS/Linux):
- Stops and removes the running container
- Does NOT remove the volume (data persists)

**`scripts/start_windows.ps1`** / **`scripts/stop_windows.ps1`**: PowerShell equivalents for Windows.

All scripts should be idempotent — safe to run multiple times.

### Optional Cloud Deployment

The container is designed to deploy to AWS App Runner, Render, or any container platform. A Terraform configuration for App Runner may be provided in a `deploy/` directory as a stretch goal, but is not part of the core build.

---

## 12. Testing Strategy

### Unit Tests (within `frontend/` and `backend/`)

**Backend (pytest)**:
- Market data: simulator generates valid prices, GBM math is correct, Massive API response parsing works, both implementations conform to the abstract interface
- Portfolio: trade execution logic, P&L calculations, edge cases (selling more than owned, buying with insufficient cash, selling at a loss)
- LLM: structured output parsing handles all valid schemas, graceful handling of malformed responses, trade validation within chat flow
- API routes: correct status codes, response shapes, error handling

**Frontend (React Testing Library or similar)**:
- Component rendering with mock data
- Price flash animation triggers correctly on price changes
- Watchlist CRUD operations
- Portfolio display calculations
- Chat message rendering and loading state

### E2E Tests (in `test/`)

**Infrastructure**: A separate `docker-compose.test.yml` in `test/` that spins up the app container plus a Playwright container. This keeps browser dependencies out of the production image.

**Environment**: Tests run with `LLM_MOCK=true` by default for speed and determinism.

**Key Scenarios**:
- Fresh start: default watchlist appears, $10k balance shown, prices are streaming
- Add and remove a ticker from the watchlist
- Buy shares: cash decreases, position appears, portfolio updates
- Sell shares: cash increases, position updates or disappears
- Portfolio visualization: heatmap renders with correct colors, P&L chart has data points
- AI chat (mocked): send a message, receive a response, trade execution appears inline
- SSE resilience: disconnect and verify reconnection

---

## 13. Review Notes — Questions, Clarifications & Simplifications

*Added by a documentation review pass. Items are grouped by how much they block work. Each question is numbered so answers can be recorded inline. Findings were checked against the already-built `backend/app/market/` code, so several items are contradictions between this plan and shipped behaviour rather than hypotheticals.*

### A. Blocking contradictions — these will produce wrong code if left as-is

**A1. "Daily change %" has no data source.**
§10 requires the watchlist to show *daily change %*. The only percentage available is `PriceUpdate.change_percent`, which is **tick-over-tick** (change since the last 500ms update) — a number that will read ±0.05% and jitter constantly. Nothing in the system records a session open or previous close.
→ *Decision needed:* add an `open_price` (captured at process start / first tick) to `PriceCache`, and emit `day_change` + `day_change_percent` alongside the existing tick fields. Otherwise change §10 to say "change since last tick" and accept that the number is visually meaningless.

**A2. The SSE payload shape in §6 doesn't match what's implemented.**
§6 says "Each SSE event contains ticker, price, previous price, timestamp, and change direction" — i.e. one event per ticker. `backend/app/market/stream.py` actually sends **one event containing a map of all tickers**: `data: {"AAPL": {...}, "GOOGL": {...}}`. The frontend agent will build the wrong parser from this document.
→ Update §6 to document the map-of-tickers payload, the `retry: 1000` directive, and the fact that events are only sent when `PriceCache.version` changes.

**A3. The LLM cannot report a failed trade in the same message.**
§9 says "If a trade fails validation, the error is included in the chat response so the LLM can inform the user." This is impossible in the described single-call flow: the LLM writes `message` *before* step 6 executes the trades. A rejected buy will still be accompanied by "Done — bought 10 AAPL."
→ *Decision needed:* either (a) render execution results as a separate structured block in the chat bubble, distinct from the LLM's prose, and word the system prompt so the model never claims completion ("I'll buy 10 AAPL" not "I bought"); or (b) make a second LLM call with the execution results. (a) is cheaper and keeps the one-call latency story. Recommend (a), and rewrite the §9 sentence accordingly.

**A4. Nothing connects the watchlist to the market data source.**
`POST /api/watchlist` writes a DB row. `MarketDataSource.add_ticker()` is a separate call. §8 and §6 never say who wires them together, and §6's "all tickers known to the system" is ambiguous.
→ Specify explicitly: **tracked tickers = watchlist ∪ tickers with a non-zero position.** This matters because removing a ticker from the watchlist while holding shares would otherwise stop its price updates and break portfolio valuation. Say so in §6, and say that watchlist mutations call through to the source.

**A5. Unknown tickers get a random price that changes on every restart.**
`simulator._add_ticker_internal` falls back to `random.uniform(50.0, 300.0)` for any ticker not in `SEED_PRICES`. §9's own example has the LLM adding PYPL. Combined with a persistent SQLite volume, a position bought at $180 can be worth $62 after a container restart — the P&L chart will show a cliff that isn't a bug in the portfolio code.
→ *Decision needed:* seed unknown tickers deterministically (hash the symbol) **and/or** persist last-known prices to the DB on shutdown and reload on start. Also decide whether arbitrary symbols are accepted at all, or validated against an allowlist. See also B3.

**A6. Timestamp formats are inconsistent across the wire.**
The DB schema (§7) uses ISO 8601 strings; `PriceUpdate.timestamp` is a float of Unix seconds. The frontend will receive both and needs two parsers.
→ Pick one convention and state it: recommend **ISO 8601 UTC everywhere in REST responses, epoch seconds only in the SSE hot path** (documented as such), or convert at the SSE boundary.

### B. Underspecified — two agents will make different, incompatible choices

**B1. Missing endpoints.** §8's table omits things the UI in §10 requires:
- `GET /api/chat/history` — §10 specifies a "scrolling conversation history" and §7 persists `chat_messages` across restarts, but there's no way to load it on page load.
- `GET /api/trades` — the `trades` table is append-only and never read. A trading terminal with no blotter is a conspicuous omission; either add the endpoint and a blotter panel, or state that trades are intentionally only visible via positions and chat.
- Portfolio reset. The volume persists, so after a demo the user is stuck with whatever the AI did to their $10k. Right now the only reset is `docker volume rm finally-data`. Either add `POST /api/portfolio/reset` or document the volume command in §11 and the README.

**B2. `GET /api/portfolio/history` takes no parameters and grows without bound.**
Snapshots every 30s = 2,880 rows/day, ~20k/week, in a volume designed to persist. The P&L chart will eventually fetch megabytes.
→ Specify `?since=` / `?limit=` (or a fixed window like "last 6 hours"), plus a retention or downsampling rule. Also worth asking: does the 30s cadence earn itself, or would 60s plus on-every-trade be indistinguishable in the chart?

**B3. Ticker validation on `POST /api/watchlist` is undefined.**
Uppercase normalisation? Length/charset limit? Duplicate handling (409 vs idempotent 200)? Max watchlist size (the Cholesky rebuild is O(n²) and the code comments assume n < 50)? What happens under `MASSIVE_API_KEY` when the symbol doesn't exist at Polygon — does the add fail, or silently produce a ticker that never prices?

**B4. Trade validation rules aren't stated.**
Needed: reject `quantity <= 0`; reject non-finite values; behaviour when the price cache has no entry for the ticker (a just-added symbol before its first tick) — reject with a clear error rather than filling at 0. Can the user trade a ticker that isn't on the watchlist (the §10 trade bar is a free-text ticker field, implying yes)? If so, does trading auto-add to the watchlist?

**B5. Money and float precision.**
Cash and quantities are `REAL`. "Sell everything" via repeated float subtraction leaves residuals like `1e-14` shares.
→ State the rule: round cash to cents on write; **delete the position row when `abs(quantity) < 1e-9`**; round displayed prices to 2dp. Also state that `avg_cost` is unchanged by sells (only buys move it) and that realized P&L is deliberately not tracked — it shows up implicitly in cash and the total-value chart.

**B6. "Total value" needs one definition.**
Define once, at the top of §7 or §8: `total_value = cash_balance + Σ(quantity × current_price)`, prices from `PriceCache`, tickers with no cached price excluded (or valued at `avg_cost` — pick one). Then say how the **header** stays live: recomputed client-side from the SSE stream, or polled from `/api/portfolio`? Only the former can update at 500ms, and if it isn't specified the two numbers on screen will disagree.

**B7. Database path and local (non-Docker) development.**
§4 says the backend writes to a volume at `/app/db`. That path doesn't exist on a developer's Mac, and agents will develop this outside Docker. §5 lists no `DATABASE_PATH` variable.
→ Add `DATABASE_PATH` to §5 with a repo-relative default (`db/finally.db`) and the container override (`/app/db/finally.db`).
Relatedly: §5 says "the backend reads `.env` from the project root", but `uv run` is executed from `backend/` — say explicitly that the loader walks up one level, or move to `--env-file`.

**B8. The dev-mode CORS claim isn't true.**
"All API calls go to the same origin — no CORS configuration needed" (§10) holds only for the built static export. During development the Next.js dev server is on :3000 and FastAPI on :8000 — different origins.
→ Document the intended dev setup: `rewrites()` in `next.config.js` proxying `/api/*` to `localhost:8000`. This is a five-line config that will otherwise cost an agent an hour.

**B9. `SQLite` concurrency is not addressed.**
There will be at least two background tasks (price source, snapshotter) plus request handlers plus LLM-triggered writes, and FastAPI async handlers calling blocking `sqlite3` will stall the event loop — including the SSE stream.
→ State the approach in §7: WAL mode, `check_same_thread=False`, DB calls dispatched to a threadpool, and a lock (or a single `BEGIN IMMEDIATE` transaction) around the read-modify-write of cash + position during a trade, since buy validation is a check-then-act race.

**B10. Chat context budget is unbounded.** §9 says "recent conversation history" without a number. Specify (e.g. last 20 messages, or a token budget), and whether tool/action results are included in history.

**B11. Behaviour without `OPENROUTER_API_KEY`.** §5 marks it required, but the app should still boot and stream prices with only the chat panel degraded. State the expected failure: startup warning, `/api/chat` returns a clear error the UI renders, everything else works.

**B12. Massive API realities are glossed over.** Three questions:
- Which Polygon endpoint? "Poll for the union of all watched tickers" at 15s on a 5-calls/min tier only works if that's **one grouped snapshot call**, not ten per-ticker calls (which would allow a poll every two minutes).
- Cadence mismatch: SSE pushes at 500ms but real data refreshes every 15s, so 29 of every 30 frames are flat. Sparklines become step functions and flashes nearly stop. Worth stating as expected behaviour so it isn't debugged as a bug.
- **Market hours.** Outside 09:30–16:00 ET and on weekends, real data is frozen and the entire terminal looks dead. This is the single biggest demo risk in the optional path. Recommend documenting it, and consider falling back to the simulator when the market is closed.

**B13. Price history survives nothing.** Sparklines and the main chart are accumulated on the frontend from SSE since page load (§2, §10), so every refresh empties both charts while the P&L chart (server-persisted) keeps its history. That asymmetry will look broken.
→ *Consider:* a bounded ring buffer (e.g. last 600 ticks/ticker ≈ 5 min) inside `PriceCache` plus `GET /api/history/{ticker}`. ~30 lines of server code, and it serves the sparkline *and* the main chart *and* survives reload. Recommended — see C4.

### C. Simplification opportunities

**C1. Two directories named `db` is a trap.** §4 has `backend/db/` (schema and seed *code*) and top-level `db/` (the SQLite *file*). Agents will conflate them, and `backend/db/` sitting outside `backend/app/` breaks the package layout the wheel build already declares (`packages = ["app"]`).
→ Move schema/seed code to `backend/app/db/` and keep top-level `db/` purely as the volume mount. One rename, removes a whole class of confusion.

**C2. Have mutating endpoints return the new state.** `POST /api/portfolio/trade`, `POST/DELETE /api/watchlist`, and `POST /api/chat` should each return the updated portfolio/watchlist. Removes a follow-up `GET` after every action and eliminates the window where the UI shows stale numbers.

**C3. Drop prices from `GET /api/watchlist`.** §8 says it returns "tickers with latest prices", but prices already arrive continuously over SSE. Two sources of truth for the same number means they will visibly disagree during the first second after load. Return tickers (and metadata) only; let SSE own price.

**C4. One price-history mechanism instead of two.** Adopting B13's server-side ring buffer collapses "sparkline data" and "main chart data" into a single endpoint and deletes the frontend's accumulate-since-page-load special case. Fewer moving parts *and* better behaviour.

**C5. One error shape.** Standardise on FastAPI's `{"detail": "..."}` for every 4xx/5xx and say so once, so the frontend has exactly one error path rather than per-endpoint handling.

**C6. Rename the scripts.** `start_mac.sh` also targets Linux (§4 says so). Call them `scripts/start.sh` / `stop.sh` and `scripts/start.ps1` / `stop.ps1`.

**C7. Note that `actions` on `chat_messages` is deliberate denormalisation.** It duplicates rows in `trades`. That's the right call for rendering inline confirmations without a join, but say it's intentional or a reviewer will file it as a bug.

### D. Docker & build details worth pinning down (§11)

- `npm install` → **`npm ci`**, which requires `frontend/package-lock.json` to be committed. Same rationale as the `uv.lock` already in the repo.
- Stage 2 should be `uv sync --frozen --no-dev` so lockfile drift fails the build and test tooling stays out of the image.
- Name the static path (`/app/static`) and specify the **SPA fallback**: unknown non-`/api` routes serve `index.html`; unknown `/api/*` routes 404 as JSON. Getting the mount order wrong here (catch-all shadowing `/api`) is the classic failure.
- `uvicorn --host 0.0.0.0` — trivial, and universally forgotten.
- Next.js `output: 'export'` disables API routes and image optimization; set `images: { unoptimized: true }` and decide on `trailingSlash` to match however FastAPI serves the files.
- Add a `HEALTHCHECK` hitting `/api/health`, and run as a non-root user.
- §3's diagram says "Background task" (singular) but there are at least two — market data and the snapshotter. Minor, but the diagram is what agents skim.

### E. Testing gaps (§12)

- **There is no CI that runs tests.** `.github/workflows/` currently contains only the two Claude Code review workflows. Nothing runs `pytest`, `ruff`, the frontend unit tests, or Playwright on a PR. Worth adding, and worth stating a coverage floor (the market data module landed at 84%).
- **E2E state isolation is unspecified.** Tests need a clean $10k/10-ticker database each run. Say how: a fresh anonymous volume per `docker-compose.test.yml` run, `DATABASE_PATH` pointed at a tmpfs, or a reset endpoint (B1).
- **"SSE resilience: disconnect and verify reconnection"** needs a stated mechanism — Playwright `context.setOffline(true)` or `page.route()` aborting the stream — otherwise the test will be written as a sleep.
- The market data path is already well covered (73 tests); the plan should name the *new* risky areas for equivalent rigour: trade validation edge cases, the LLM structured-output parser against malformed/partial JSON, and concurrent trade + snapshot writes.

### F. Housekeeping

- **`.env.example` is referenced in §4 as committed but does not exist in the repo.** It's the first thing a new user needs. Should list `OPENROUTER_API_KEY`, `MASSIVE_API_KEY`, `LLM_MOCK`, and (per B7) `DATABASE_PATH`.
- Seed prices (AAPL ~$190 etc.) are anchored to an older market. Harmless for the simulator, but if a user sets `MASSIVE_API_KEY` mid-session prices will jump discontinuously. One sentence in §6 is enough.
- §2 promises "the user runs a single Docker command (or a provided start script)" and "a browser opens" — confirm whether the start script auto-opens the browser (§11 says "optionally"). Pick one so the README is accurate.
- **The agent handoff contract is asserted but not defined.** §1 says "Agents interact through files in `planning/`" without specifying how. The market data component established a good pattern worth codifying: publish an interface/design doc *before* implementing, and a `<COMPONENT>_SUMMARY.md` after, with the older docs moved to `planning/archive/`. Since demonstrating orchestrated agents is the entire point of the project, this convention deserves to be stated rather than inferred.
