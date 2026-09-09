# FinAlly — AI Trading Workstation

A visually stunning AI-powered trading workstation that streams live market data, simulates portfolio trading, and integrates an LLM chat assistant that can analyze positions and execute trades via natural language.

Built entirely by coding agents as a capstone project for an agentic AI coding course.

## Features

- **Live price streaming** via SSE with green/red flash animations
- **Simulated portfolio** — $10k virtual cash, market orders, instant fills
- **Portfolio visualizations** — heatmap (treemap), P&L chart, positions table
- **AI chat assistant** — analyzes holdings, suggests and auto-executes trades
- **Watchlist management** — track tickers manually or via AI
- **Dark terminal aesthetic** — Bloomberg-inspired, data-dense layout

## Architecture

Single Docker container serving everything on port 8000:

- **Frontend**: Next.js (static export) with TypeScript and Tailwind CSS
- **Backend**: FastAPI (Python/uv) with SSE streaming
- **Database**: SQLite with lazy initialization
- **AI**: LiteLLM → OpenRouter (Cerebras inference) with structured outputs
- **Market data**: Built-in GBM simulator (default) or Massive API (optional)

## Quick Start

```bash
# Clone and configure
cp .env.example .env
# Add your OPENROUTER_API_KEY to .env

# Run with Docker
docker build -t finally .
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally

# Open http://localhost:8000
```

Or use the provided start/stop scripts, which wrap the same `docker build`/
`docker run` commands, are safe to run repeatedly, and (on macOS/Linux) open
your browser automatically:

```bash
# macOS / Linux
scripts/start.sh
scripts/stop.sh          # stops the container; your data is untouched

# Windows (PowerShell)
scripts\start.ps1
scripts\stop.ps1
```

`docker compose up` (using the included `docker-compose.yml`) is an
equivalent convenience wrapper if you prefer Compose.

### Resetting your data

The SQLite database lives in the `finally-data` Docker volume, so it
survives container restarts and `scripts/stop.sh`/`docker stop`. To wipe it
and start over with a fresh $10k/10-ticker database:

```bash
scripts/stop.sh          # or: docker stop finally && docker rm finally
docker volume rm finally-data
scripts/start.sh          # re-creates the volume, seeded fresh on first request
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for AI chat |
| `MASSIVE_API_KEY` | No | Massive (Polygon.io) key for real market data; omit to use simulator |
| `LLM_MOCK` | No | Set `true` for deterministic mock LLM responses (testing) |
| `DATABASE_PATH` | No | SQLite file path. Defaults to `db/finally.db` locally; the Docker image sets this to `/app/db/finally.db` internally |

## Project Structure

```
finally/
├── frontend/    # Next.js static export
├── backend/     # FastAPI uv project
├── planning/    # Project documentation and agent contracts
├── test/        # Playwright E2E tests
├── db/          # SQLite volume mount (runtime)
└── scripts/     # Start/stop helpers
```

## License

See [LICENSE](LICENSE).
