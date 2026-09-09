#!/usr/bin/env bash
# FinAlly — start the app (Linux/macOS). See PLAN.md §11, §13.C6.
#
# Idempotent: safe to run repeatedly.
#   - If the container is already running, prints the URL and exits.
#   - If it exists but is stopped, restarts it (no rebuild).
#   - Otherwise builds the image and creates the container.
#
# Usage:
#   scripts/start.sh              # build only if the image doesn't exist yet
#   scripts/start.sh --build      # force a rebuild even if the image exists
#
# Reset (wipe the database, keep the image): docker volume rm finally-data
# (the container must be stopped first — run scripts/stop.sh).

set -euo pipefail

IMAGE_NAME="finally"
CONTAINER_NAME="finally"
VOLUME_NAME="finally-data"
PORT="${PORT:-8000}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

FORCE_BUILD=false
if [[ "${1:-}" == "--build" ]]; then
  FORCE_BUILD=true
fi

if [[ ! -f .env ]]; then
  echo "Warning: .env not found. Copy .env.example to .env and add your" >&2
  echo "OPENROUTER_API_KEY before chat will work (the rest of the app still" >&2
  echo "runs without it)." >&2
fi

# If already running, nothing to do.
if [[ -n "$(docker ps -q --filter "name=^/${CONTAINER_NAME}$")" ]]; then
  echo "FinAlly is already running at http://localhost:${PORT}"
  exit 0
fi

if ${FORCE_BUILD} || [[ -z "$(docker images -q "${IMAGE_NAME}" 2>/dev/null)" ]]; then
  echo "Building image ${IMAGE_NAME}..."
  docker build -t "${IMAGE_NAME}" "${REPO_ROOT}"
fi

# Named volume is idempotent to create even if it already exists.
docker volume create "${VOLUME_NAME}" >/dev/null

# If a stopped container from a previous run exists, just restart it rather
# than re-creating (preserves the exact run config used to create it).
if [[ -n "$(docker ps -aq --filter "name=^/${CONTAINER_NAME}$")" ]]; then
  echo "Restarting existing container ${CONTAINER_NAME}..."
  docker start "${CONTAINER_NAME}" >/dev/null
else
  echo "Creating container ${CONTAINER_NAME}..."
  ENV_FILE_ARGS=()
  if [[ -f .env ]]; then
    ENV_FILE_ARGS=(--env-file .env)
  fi
  docker run -d \
    --name "${CONTAINER_NAME}" \
    -p "${PORT}:8000" \
    -v "${VOLUME_NAME}:/app/db" \
    "${ENV_FILE_ARGS[@]}" \
    "${IMAGE_NAME}" >/dev/null
fi

echo "FinAlly is running at http://localhost:${PORT}"

# Best-effort browser open (PLAN §11: "optionally"). Never fails the script.
if command -v open >/dev/null 2>&1; then
  open "http://localhost:${PORT}" >/dev/null 2>&1 || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://localhost:${PORT}" >/dev/null 2>&1 || true
fi
