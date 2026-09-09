#!/usr/bin/env bash
# FinAlly — stop the app (Linux/macOS). See PLAN.md §11, §13.C6.
#
# Idempotent: safe to run repeatedly, including when nothing is running.
# Stops and removes the container only. Does NOT remove the "finally-data"
# volume — your portfolio, watchlist, and chat history persist across
# start/stop cycles.
#
# To fully reset the app's data (irreversible):
#   scripts/stop.sh
#   docker volume rm finally-data

set -euo pipefail

CONTAINER_NAME="finally"

if [[ -n "$(docker ps -aq --filter "name=^/${CONTAINER_NAME}$")" ]]; then
  echo "Stopping ${CONTAINER_NAME}..."
  docker stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  docker rm "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  echo "Stopped. Data preserved in the 'finally-data' volume."
else
  echo "FinAlly is not running (nothing to do)."
fi
