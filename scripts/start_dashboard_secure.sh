#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"

# Stop launchd-managed dashboard (if running) to avoid port conflicts.
"${PROJECT_ROOT}/scripts/dashboard_service.sh" stop >/dev/null 2>&1 || true

# Kill remaining local dashboard listeners on 8000 from this project.
listeners="$(lsof -ti tcp:8000 -sTCP:LISTEN || true)"
if [[ -n "${listeners}" ]]; then
  for pid in ${listeners}; do
    cmd="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
    if [[ "${cmd}" == *"instagram-ai-bot"* || "${cmd}" == *"dashboard.py"* ]]; then
      kill "${pid}" >/dev/null 2>&1 || true
    fi
  done
  sleep 1
fi

exec "${PROJECT_ROOT}/scripts/with_secrets.sh" \
  "${PYTHON_BIN}" "${PROJECT_ROOT}/dashboard.py" --host 127.0.0.1 --port 8000
