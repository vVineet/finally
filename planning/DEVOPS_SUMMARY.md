# FinAlly — DevOps Summary

Status: **partial pass, as scoped**. `frontend/` was being created concurrently
by the Frontend Engineer during this stage and does not yet have
`output: 'export'` configured, so the real multi-stage image cannot build
end-to-end yet. Every artifact below is written complete and correct, as if
the frontend export existed; everything verifiable without it was actually
run, not just written. See "What remains unverified" for the exact list of
what needs a second pass once the frontend lands.

Design rationale for every decision below was published first in
`planning/DEVOPS_DESIGN.md` (per PLAN §13.F's agent-handoff convention).
This document covers what was actually built and the real results of
running it.

## What was built

```
Dockerfile              Multi-stage: node:20-slim (frontend export) ->
                         python:3.12-slim (uv-managed FastAPI + static mount)
.dockerignore            Build-context exclusions
docker-compose.yml       Optional convenience wrapper (PLAN §11 marks optional)
scripts/start.sh         Linux/macOS start (§13.C6 rename from start_mac.sh)
scripts/stop.sh          Linux/macOS stop -- never removes the volume
scripts/start.ps1        Windows PowerShell equivalent
scripts/stop.ps1         Windows PowerShell equivalent
.env.example             OPENROUTER_API_KEY, MASSIVE_API_KEY, LLM_MOCK,
                         DATABASE_PATH (did not exist before this stage)
db/.gitkeep              Volume mount point (did not exist before this stage)
.gitignore               +2 lines: db/*.db, db/*.db-* (see below)
.github/workflows/tests.yml   New CI workflow: pytest+ruff (backend),
                         unit tests (frontend); does not touch the two
                         existing Claude review workflows
README.md                +scripts usage, +docker volume rm reset path,
                         +DATABASE_PATH row in the env var table
```

## Binding decisions — how each was implemented

- **`npm ci`, not `npm install`** (§13.D): Dockerfile stage 1 uses `npm ci`
  against `frontend/package.json` + `frontend/package-lock.json`.
  **Confirmed unblocked**: `frontend/package-lock.json` already exists
  (236KB), committed by the Frontend Engineer, verified by reading it
  directly from disk in this stage.
- **`uv sync --frozen --no-dev`** (§13.D): in stage 2, fails the build on
  lockfile drift, excludes the `dev` extra. Verified for real (see below) —
  and this surfaced two real bugs, fixed before this report:
  1. `uv sync` failed even outside Docker with `OSError: Readme file does
     not exist: README.md` — `backend/pyproject.toml` declares
     `readme = "README.md"`, and hatchling validates that field during
     `uv sync --no-dev`, not just on an explicit build. Fixed by also
     copying `backend/README.md` alongside `pyproject.toml`/`uv.lock` before
     the `RUN uv sync` layer.
  2. On the note "httpx must NOT end up in the production image": it does
     end up there anyway, and that's correct, not a bug. `httpx` is a
     transitive runtime dependency of `openai` (used by `litellm`) — three
     other packages in `uv.lock` depend on it (grep confirmed) independent
     of the `dev` extra. `--no-dev` only removes the *explicit* dev-extra
     pin (`{ name = "httpx", marker = "extra == 'dev'" }`); it cannot and
     should not remove a dependency other production packages require.
     Flagging this so nobody re-opens it as a bug later: `pytest`, `ruff`,
     and `pytest-asyncio`/`pytest-cov` are confirmed absent from the
     `--no-dev` install (see verification output below); `httpx` is
     confirmed present, and that's expected.
- **Static path `/app/static`**: read `backend/app/main.py`'s
  `_static_dir()` directly — it defaults to `STATIC_DIR` env var, else
  `_BACKEND_ROOT/static` where `_BACKEND_ROOT` is two parents up from
  `main.py`. Given this Dockerfile's copy layout (`backend/app` →
  `/app/app`), that default already resolves to `/app/static`; the
  Dockerfile also sets `STATIC_DIR=/app/static` explicitly so the path
  stays correct even if the internal copy layout changes later, without
  requiring a reader to re-derive it. No backend code was touched.
- **SPA fallback**: already implemented in `backend/app/main.py` (verified
  by reading it, not modified) — `/api/*` routers registered before the
  catch-all static mount, uniform `{"detail": ...}` JSON for unmatched
  `/api/*`, `index.html` for any other unmatched path when a static build
  exists, plain JSON 404 when it doesn't. Confirmed live in the backend-only
  verification container (see below): an unmatched non-`/api` path returned
  `{"detail":"Not Found"}` / 404 because no static build was present in that
  throwaway image, exactly as documented — nothing crashed.
- **`uvicorn --host 0.0.0.0`**: in the `CMD`. Verified live (curl from the
  host machine reached the container through the port mapping).
- **`HEALTHCHECK` hitting `/api/health`, non-root user**: both implemented
  and verified live — see below. One real bug found and fixed: `useradd
  --system --uid 1000 ...` printed `uid 1000 is greater than SYS_UID_MAX
  999` (a `--system` user is expected to stay under 1000). Fixed by
  dropping `--system` and creating a plain uid/gid-1000 user instead (the
  conventional non-root container uid) — rebuilt clean, no warning.
- **`DATABASE_PATH=/app/db/finally.db`**: set via `ENV` in the Dockerfile.
  Matches `backend/app/db/connection.py`'s own contract (reads
  `DATABASE_PATH` fresh every call, falls back to a repo-relative default
  only when unset) — read directly, not guessed.
- **`docker volume rm finally-data` reset path**: documented in
  `scripts/stop.sh`'s header comment, `scripts/start.sh`'s header comment,
  and a new "Resetting your data" section in `README.md`.
- **Scripts renamed per §13.C6**: `scripts/start.sh` / `stop.sh` /
  `start.ps1` / `stop.ps1` (no `_mac` suffix). All four are idempotent by
  construction (name-based existence checks before every mutating command);
  idempotency was verified live for the two Linux/macOS scripts (see
  below), not just asserted from reading the code. `stop.sh` never issues
  `docker volume rm` — verified the volume and its contents survived a
  full stop → start cycle.

## What was actually run (real output)

All of the following ran with `dangerouslyDisableSandbox` — the default
sandbox blocks the Docker Unix socket (`permission denied ... docker.sock`)
and the `uv` cache directory; both are legitimate local-verification needs,
not a workaround of anything the user restricted.

**1. `uv sync --frozen --no-dev` against the real `backend/pyproject.toml` +
`backend/uv.lock`**, in an isolated temp copy (not inside `backend/`, per
scope):

```
$ uv sync --frozen --no-dev
Installed 72 packages
SYNC EXIT:0
```
```
$ .venv/bin/python -c "import pytest"      -> ModuleNotFoundError: No module named 'pytest'   (correctly ABSENT)
$ .venv/bin/python -c "import ruff"        -> ModuleNotFoundError: No module named 'ruff'      (correctly ABSENT)
$ .venv/bin/python -c "import fastapi, uvicorn, numpy, litellm"  -> prod deps import OK
```
(`httpx` *is* present — expected, see above.)

**2. Built a throwaway single-stage Dockerfile that mirrors Stage 2 of the
real `Dockerfile` exactly**, from the real build context (repo root), to
prove the Python stage works without needing `frontend/out/` to exist. Not
committed — the real `Dockerfile` is the deliverable, and it can't fully
build until the frontend lands.

```
$ docker build -f <tmp>/Dockerfile.backend-only -t finally-backend-verify .
...
 => [7/7] RUN groupadd --gid 1000 finally && useradd ... && chown -R    17.6s
 => exporting to image                                                  17.6s
```
(clean build, no warnings, after the two fixes above.)

**3. Ran the resulting image with a real named volume and verified, live**:

```
$ docker exec finally-verify-run whoami
finally
$ docker exec finally-verify-run id
uid=1000(finally) gid=1000(finally) groups=1000(finally)

$ docker exec finally-verify-run sh -c "touch /app/db/write-test && ls -la /app/db"
-rw-r--r-- 1 finally finally 0 ... write-test        # non-root user CAN write the volume

$ curl http://localhost:18000/api/health
{"status":"ok"}                                       # 200, host -> container port mapping works

$ curl http://localhost:18000/some/spa/route
{"detail":"Not Found"}  HTTP_STATUS:404                # graceful degrade, no static dir in this image

$ curl http://localhost:18000/api/does-not-exist
{"detail":"Not Found"}  HTTP_STATUS:404                # uniform error shape on an unmatched /api path

$ docker inspect --format='{{.State.Health.Status}}' finally-verify-run
healthy                                                # HEALTHCHECK passes end-to-end
```

**4. Tagged the verified image as `finally` and ran the real
`scripts/start.sh` / `scripts/stop.sh` against it** (the actual files in
this repo, unmodified for the test):

```
$ bash scripts/start.sh          # image already present -> build skipped
Creating container finally...
FinAlly is running at http://localhost:18001

$ bash scripts/start.sh          # 2nd call: idempotent
FinAlly is already running at http://localhost:18001

$ docker exec finally sh -c "echo hello > /app/db/marker.txt"

$ bash scripts/stop.sh
Stopping finally...
Stopped. Data preserved in the 'finally-data' volume.

$ docker ps -a --filter name='^/finally$'   # confirmed empty -- container removed
$ docker volume ls --filter name=finally-data   # confirmed present -- volume NOT removed

$ bash scripts/stop.sh           # 2nd call on an already-stopped app: idempotent
FinAlly is not running (nothing to do).

$ bash scripts/start.sh          # re-creates the container fresh
$ docker exec finally cat /app/db/marker.txt
hello                            # confirms data survived a full stop -> volume-intact -> start cycle
```

All throwaway resources (`finally-verify-run`, the retagged `finally`
image, `finally-backend-verify` image, the `finally-data` test volume) were
removed afterward; nothing was left running or lying around from this
verification pass.

**5. `docker-compose.yml` validated with `docker compose config`** — resolved
cleanly (build context, port mapping, volume, healthcheck all parsed as
intended). Not run with `up` since that would build the same
not-yet-buildable multi-stage image.

**6. `.gitignore` / `db/.gitkeep` interaction**, verified with real files:

```
$ touch db/finally.db db/finally.db-wal db/finally.db-shm
$ git check-ignore -v db/finally.db db/finally.db-wal
.gitignore:67:db/*.db     db/finally.db
.gitignore:68:db/*.db-*   db/finally.db-wal
$ git status --porcelain --ignored db/     # only db/.gitkeep shows as untracked-but-real; the .db files don't appear at all
```
(test files removed afterward.)

**7. Script syntax**: `bash -n scripts/start.sh` and `bash -n scripts/stop.sh`
both pass. `pwsh` is not installed on this machine, so `start.ps1`/`stop.ps1`
could not be syntax-checked with the PowerShell parser itself — written
carefully by hand, mirroring the already-verified `.sh` logic 1:1, but this
is the one script-level check that's genuinely unverified (listed below,
not hidden).

## What remains unverified (deferred to the follow-up pass)

1. **The real multi-stage `Dockerfile` end-to-end.** `frontend/next.config.ts`
   does not yet set `output: 'export'` (confirmed by reading the file — it's
   still the scaffold default), so `npm run build` in stage 1 will not
   produce `frontend/out/`, and the real `docker build -t finally .` cannot
   succeed yet. Everything stage 2 does was proven separately (see above);
   what's unverified is specifically the handoff between the two stages —
   that `COPY --from=frontend-builder /app/frontend/out ./static` actually
   finds files there once the frontend sets `output: 'export'`.
2. **`docker-compose up`** end-to-end (blocked by the same dependency).
3. **The SPA fallback serving real `index.html` content** for a client-side
   route — proven only that it degrades correctly when no static build
   exists; not proven against an actual built export yet.
4. **`trailingSlash`** — `planning/FRONTEND_SUMMARY.md` does not exist yet,
   so whatever the Frontend Engineer decides is unknown. No Dockerfile
   change is anticipated either way, but worth a joint check once that file
   lands in case the static export's internal links and the backend's SPA
   fallback disagree on trailing slashes.
5. **`start.ps1` / `stop.ps1`** — written to mirror the verified `.sh`
   logic exactly, but not run through a PowerShell parser or a real Windows
   Docker Desktop instance (neither available in this environment).
6. **The new CI workflow (`tests.yml`)** has not run on an actual GitHub
   Actions runner (no push/PR triggered from this stage) — its YAML
   structure was hand-reviewed and its constituent commands
   (`uv sync --extra dev`, `uv run pytest -q`, `uv run ruff check`, `npm ci`)
   were exercised locally in isolation (see the pytest/ruff run in
   `planning/BACKEND_SUMMARY.md`, and the `npm ci` / lockfile presence
   confirmed above), but the workflow file itself is unverified until a PR
   actually runs it. The frontend `npm test --if-present` step is a no-op
   today since `frontend/package.json` has no `test` script yet — expected,
   not a bug, and explained in `planning/DEVOPS_DESIGN.md`.

## Constraints honored

- No changes to `backend/` or `frontend/` application code — the two real
  bugs found (README.md needed by `uv sync`, `useradd --system` uid warning)
  were both fixed entirely within `Dockerfile`, not by touching `backend/`.
- `.gitignore` and `README.md` are not in the explicit owned-files list for
  this task, but both changes are one-line/small additions directly required
  by files that are in scope (`db/.gitkeep` needs the `.gitignore` entries to
  serve its purpose; the task explicitly asked for the reset path to be
  documented in the README) — noted here rather than silently expanding
  scope.
- Did not run `git commit` — left for review as instructed.

## Files touched

- `Dockerfile`, `.dockerignore`, `docker-compose.yml` (new)
- `scripts/start.sh`, `scripts/stop.sh`, `scripts/start.ps1`,
  `scripts/stop.ps1` (new)
- `.env.example` (new)
- `db/.gitkeep` (new)
- `.gitignore` (+2 lines)
- `.github/workflows/tests.yml` (new; `claude.yml` and
  `claude-code-review.yml` untouched)
- `README.md` (scripts usage, reset path, `DATABASE_PATH` row)
- `planning/DEVOPS_DESIGN.md`, `planning/DEVOPS_SUMMARY.md` (new)
