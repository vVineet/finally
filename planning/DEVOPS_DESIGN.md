# FinAlly — DevOps Design

Status: **design, pre-implementation**. Published before writing any
Docker/CI/script artifacts, per the agent handoff convention (PLAN §13.F).
Written against `backend/app/main.py` and `planning/BACKEND_SUMMARY.md` as
they exist right now; `frontend/` is being created concurrently by the
Frontend Engineer and does not yet have `output: 'export'` configured (see
"Open dependency on the frontend" below).

## Scope (what this document covers)

`Dockerfile`, `.dockerignore`, `docker-compose.yml`, `scripts/{start,stop}.{sh,ps1}`,
`.env.example`, top-level `db/.gitkeep`, `.github/workflows/tests.yml`. No
changes to `backend/` or `frontend/` application code.

## 1. Multi-stage Dockerfile

**Stage 1 — `node:20-slim` (`frontend-builder`)**
- `WORKDIR /app/frontend`
- `COPY frontend/package.json frontend/package-lock.json ./` then `npm ci`
  (not `npm install` — PLAN §13.D; requires the lockfile committed, confirmed
  present at `frontend/package-lock.json`, 236KB, as of this writing).
- `COPY frontend/ ./` then `npm run build`.
- Assumption, flagged as an open dependency below: this produces a static
  export at `frontend/out/` (Next's default export directory when
  `output: 'export'` is set in `next.config.ts`). That flag is not yet
  present in the repo.

**Stage 2 — `python:3.12-slim` (`backend`)**
- Install `uv` via `pip install uv` (simplest, no extra registry pull; a
  pinned version is a reasonable future hardening but not required for
  `--frozen` to do its job — the lockfile pins the actual package graph).
- `WORKDIR /app`. Copy only `backend/pyproject.toml` and `backend/uv.lock`
  first (layer caching), then `uv sync --frozen --no-dev` — fails the build
  on lockfile drift and excludes the `dev` extra (`pytest`, `ruff`,
  `httpx` — httpx was added to `dev` specifically for `TestClient` and must
  not reach the image per the task brief).
- Copy `backend/app` to `/app/app` (the importable package; nothing else
  from `backend/` — no `tests/`, no `market_data_demo.py`, no `.venv`).
- Copy the frontend build output from stage 1 into `/app/static`.
- Set `STATIC_DIR=/app/static` explicitly as an env var rather than relying
  on `backend/app/main.py`'s default-derivation (`_BACKEND_ROOT/static`,
  which *also* resolves to `/app/static` given this copy layout — the env
  var is redundant with that default today, but pinning it explicitly means
  the path stays correct even if the internal copy layout changes later,
  and it documents the contract inline rather than requiring a reader to
  trace `_static_dir()`).
- `DATABASE_PATH=/app/db/finally.db` (per the DB layer's own documented
  contract in `backend/app/db/connection.py`: it reads `DATABASE_PATH` fresh
  on every call and falls back to a repo-relative path only when unset).
- Non-root user: create a system user, `mkdir -p /app/db` and `chown` it to
  that user **before** dropping privileges. This matters specifically
  because Docker seeds a brand-new named volume's initial contents from
  whatever is already at the mount point in the image — if `/app/db` is
  owned by root with default perms when the volume is first created, the
  non-root process can never write to it. Chowning at build time is what
  makes that work.
- `HEALTHCHECK` against `GET /api/health` using `python -c
  "urllib.request.urlopen(...)"` rather than `curl` — avoids adding a
  package to a slim image for a single HTTP GET.
- `CMD` invokes the venv's `uvicorn` directly (`/app/.venv/bin/uvicorn`)
  rather than `uv run uvicorn` — avoids any runtime dependency on `uv`
  attempting a lock check/sync at container start; the venv built during
  `uv sync --frozen --no-dev` is self-contained.
- `uvicorn app.main:app --host 0.0.0.0 --port 8000` — the host bind is
  called out explicitly per the brief; it is the most common thing to
  forget and the symptom (container "works" locally, unreachable from the
  host) is confusing to debug.

### SPA fallback / static path coordination

Already implemented in `backend/app/main.py` (not something this stage
needs to build): `/api/*` routers are registered before the catch-all
static `Mount("/")`, so no ordering bug is possible; unmatched `/api/*`
paths get the uniform `{"detail": ...}` 404 JSON via the shared exception
handler, and any other unmatched path serves `index.html` if the static
directory exists (SPA client-side routing), else a plain JSON 404. This
Dockerfile only has to put the built export at the path the backend already
looks in — no backend change requested or made.

## 2. `.dockerignore`

Excludes both projects' local dev artifacts from the build context:
`node_modules`, `.next`, `frontend/out` (regenerated fresh in stage 1 —
never trust a locally-built copy that might be stale or built with the
wrong `output` mode), Python `.venv`/`__pycache__`/`.pytest_cache`/
`.ruff_cache`/`.coverage`, `db/*.db*`, `.env`, `.git`, `planning/`, `test/`
(Playwright E2E infra, irrelevant to the production image), and the two
Claude workflow/plugin directories under `.claude/`.

## 3. `docker-compose.yml`

A convenience wrapper only (PLAN §11 marks this optional) — builds from the
local `Dockerfile`, maps `8000:8000`, mounts the named volume
`finally-data` at `/app/db`, reads `.env` via `env_file`, and declares the
same healthcheck as the image (compose doesn't inherit `HEALTHCHECK` from
the Dockerfile in older versions, and being explicit costs nothing).
`restart: unless-stopped` so a demo left running survives an unrelated
Docker Desktop restart without manual intervention.

## 4. Scripts (§13.C6 rename)

`scripts/start.sh` / `stop.sh` / `start.ps1` / `stop.ps1` — not `_mac`
suffixed; PLAN §4's naming was wrong since these also target Linux.

- **`start.sh`**: idempotent — if a container named `finally` is already
  running, prints the URL and exits 0 without erroring; if it exists but is
  stopped, `docker start`s it rather than re-creating; otherwise builds
  (`docker build -t finally .`, always, so `--build` flag re-forces this)
  and `docker run -d --name finally -p 8000:8000 -v finally-data:/app/db
  --env-file .env finally`. Warns (does not fail) if `.env` is missing,
  pointing at `.env.example`. Prints `http://localhost:8000` and makes a
  best-effort attempt to open a browser (`open` on macOS, `xdg-open` on
  Linux) — failure to find either command is silently ignored, matching
  PLAN §11's "optionally open the browser."
- **`stop.sh`**: idempotent — stops and removes the `finally` container if
  it exists (no error if it doesn't); **never** touches the `finally-data`
  volume. Reset path (`docker volume rm finally-data`) is documented in the
  script's own comment header, in `.env.example`'s neighbor README section,
  and restated in `DEVOPS_SUMMARY.md`.
- **`start.ps1` / `stop.ps1`**: same behavior, PowerShell syntax, for
  Windows.

## 5. `.env.example`

Four variables, per PLAN §5 and §13.B7/F: `OPENROUTER_API_KEY`,
`MASSIVE_API_KEY`, `LLM_MOCK`, `DATABASE_PATH` (repo-relative default
`db/finally.db`, matching `backend/app/db/connection.py`'s own fallback —
the Docker image overrides this to `/app/db/finally.db` via the
`Dockerfile`'s `ENV`, not via this file, so a developer copying
`.env.example` to `.env` for local (non-Docker) work gets the correct
local-filesystem default).

## 6. `db/.gitkeep`

Empty marker file so the mount-point directory exists in a fresh checkout
(Docker will happily create `/app/db` inside the container regardless, but
`db/` also needs to exist at the repo root for local, non-Docker backend
runs that rely on `DATABASE_PATH`'s repo-relative default). Paired with two
new lines in the root `.gitignore` (`db/*.db` and `db/*.db-*`) so the actual
SQLite file and its WAL/SHM sidecars never get committed, while
`db/.gitkeep` itself is untouched by that pattern. `.gitignore` isn't in
this task's owned-files list, but it's a one-line change directly required
to make `db/.gitkeep`'s own purpose work, and touches no application code.

## 7. CI (`.github/workflows/tests.yml`)

New file, added alongside (not replacing) the two existing Claude review
workflows. Two jobs on `pull_request` (and `push` to `main`):

- **`backend`**: `astral-sh/setup-uv`, `uv sync --extra dev` (dev deps
  included here, unlike the Dockerfile), `uv run ruff check app tests`,
  `uv run pytest -q`, all with `working-directory: backend`.
- **`frontend`**: `actions/setup-node@v4` (node 20, npm cache keyed off
  `frontend/package-lock.json`), `npm ci`, `npm run lint --if-present`,
  `npm test --if-present`.

`--if-present` on the frontend steps is a deliberate call: at the time this
workflow is written, `frontend/package.json` has no `test` script yet (the
Frontend Engineer is building concurrently, PLAN §12 assigns them React
Testing Library unit tests). Using `npm test` unconditionally would turn
every unrelated PR red today for a reason that has nothing to do with the
PR's own changes. `--if-present` means: no script yet → step passes
trivially and does nothing; script added later → this same workflow file
starts actually running it, with no further edits needed. This is flagged
explicitly in `DEVOPS_SUMMARY.md` as something to double check once the
Frontend Engineer's summary lands — if their test command isn't a
plain `npm test`/`npm run test` invocation (e.g. requires `-- --run` for
Vitest in CI), this step will need a follow-up.

## Open dependency on the frontend (cannot be resolved by this agent)

- `frontend/next.config.ts` does not yet set `output: 'export'` or
  `images: { unoptimized: true }` (confirmed by reading the file directly —
  it's still the scaffold default). Without `output: 'export'`, `npm run
  build` will not produce `frontend/out/`, and the Dockerfile's `COPY
  --from=frontend-builder /app/frontend/out ./static` will fail. This
  Dockerfile is written as if that config exists, per the task's explicit
  instruction not to stub around the frontend's absence.
- `planning/FRONTEND_SUMMARY.md` does not exist yet, so the `trailingSlash`
  decision it's expected to record is unknown. This has no effect on the
  Dockerfile itself, but affects whether the backend's existing SPA
  fallback and the static export's internal links agree on trailing
  slashes — worth a joint check once that file lands, not something to
  guess at here.
- `frontend/package-lock.json` **does** already exist (verified, 236KB),
  so the `npm ci` decision is unblocked.

## What gets verified in this pass vs. deferred

Verifiable now, without a frontend: `uv sync --frozen --no-dev` against the
real `backend/pyproject.toml`/`uv.lock` (in an isolated copy, so as not to
touch anything under `backend/`), `.env.example` content, script syntax and
idempotency (`bash -n`, dry-run invocations against a throwaway container
name), the CI YAML's validity, and a backend-only Docker image built from a
temporary single-stage Dockerfile variant that mirrors stage 2 exactly
(proves the Python stage, the non-root/volume permission setup, and the
healthcheck all work) — kept as a throwaway, not committed, since the real
multi-stage `Dockerfile` is the deliverable and it cannot fully build until
`frontend/out/` exists.

Deferred to the follow-up pass once the frontend lands: the actual
multi-stage build end-to-end, `docker-compose up`, and confirming the SPA
fallback serves real `index.html` content for a client-side route.
