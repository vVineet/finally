# syntax=docker/dockerfile:1
#
# FinAlly — single-container image (PLAN.md §11, §13.D).
#
# Stage 1 builds the Next.js static export. Stage 2 runs FastAPI (uv-managed)
# and serves that export as static files on the same port (8000). See
# planning/DEVOPS_DESIGN.md for the full rationale behind each decision
# below; this file intentionally does not re-derive it inline beyond short
# pointers.

############################################
# Stage 1: frontend-builder (node:20-slim)
############################################
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# `npm ci`, not `npm install` (PLAN §13.D) — requires frontend/package-lock.json
# committed, which it is. npm ci fails loudly on a lockfile/package.json
# mismatch instead of silently rewriting the lockfile.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Expected to produce a static export at ./out (Next's `output: 'export'`).
RUN npm run build

############################################
# Stage 2: backend runtime (python:3.12-slim)
############################################
FROM python:3.12-slim AS backend

# uv installs Python deps from the committed lockfile in the next step.
RUN pip install --no-cache-dir uv

WORKDIR /app

# Dependency manifests first for layer caching. README.md is required too --
# pyproject.toml declares it as the package `readme`, and hatchling
# validates that field even for `uv sync --no-dev` (build fails otherwise:
# "OSError: Readme file does not exist: README.md" -- found by actually
# building this image, see planning/DEVOPS_SUMMARY.md).
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
# --frozen: fail the build on lockfile drift rather than silently updating it.
# --no-dev: excludes the `dev` extra (pytest, ruff, httpx) from the image.
RUN uv sync --frozen --no-dev

# Application code — only the importable package, not tests/ or the demo script.
COPY backend/app ./app

# Built frontend export from stage 1, placed at the path the backend's
# static mount is pinned to via STATIC_DIR below.
COPY --from=frontend-builder /app/frontend/out ./static

ENV STATIC_DIR=/app/static \
    DATABASE_PATH=/app/db/finally.db \
    PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Non-root user. /app/db is created and chowned *before* switching users so
# that when Docker first creates the named volume mounted at /app/db, the
# volume inherits ownership this user can write to (the classic way a
# non-root container silently fails to persist data).
# Plain (non-`--system`) user/group: uid/gid 1000 is outside useradd's
# default SYS_UID_MAX (999), which --system expects and warns about --
# found by actually building this image, see planning/DEVOPS_SUMMARY.md.
RUN groupadd --gid 1000 finally && \
    useradd --uid 1000 --gid finally --home-dir /app --no-create-home --shell /usr/sbin/nologin finally && \
    mkdir -p /app/db && \
    chown -R finally:finally /app

USER finally

EXPOSE 8000

# Hits GET /api/health. Uses python's stdlib instead of curl to avoid adding
# a package to a slim image for a single HTTP GET.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)" || exit 1

# --host 0.0.0.0 is required for the container's port mapping to reach the
# process inside — universally forgotten, called out explicitly per brief.
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
