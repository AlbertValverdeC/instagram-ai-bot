#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
VAULT_SCRIPT="${PROJECT_ROOT}/scripts/secrets_vault.py"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Error: python not found at ${PYTHON_BIN}"
  exit 1
fi

if [[ $# -eq 0 ]]; then
  cat <<'EOF'
Usage:
  scripts/with_secrets.sh <command> [args...]

Example:
  scripts/with_secrets.sh python dashboard.py --host 127.0.0.1 --port 8000
EOF
  exit 1
fi

exec "${PYTHON_BIN}" "${VAULT_SCRIPT}" exec -- "$@"
