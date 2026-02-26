#!/usr/bin/env bash
set -euo pipefail

LABEL="com.instagram-ai-bot.dashboard"
UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
LOG_DIR="${PROJECT_ROOT}/logs"
OUT_LOG="${LOG_DIR}/dashboard_service.out.log"
ERR_LOG="${LOG_DIR}/dashboard_service.err.log"

usage() {
  cat <<'EOF'
Usage: scripts/dashboard_service.sh <install|start|stop|restart|status|logs|uninstall>

Commands:
  install    Create/update LaunchAgent and start service
  start      Start or kickstart service
  stop       Stop service
  restart    Restart service
  status     Show launchd status
  logs       Tail service logs
  uninstall  Stop service and remove LaunchAgent plist
EOF
}

ensure_prereqs() {
  if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Error: python not found at ${PYTHON_BIN}"
    exit 1
  fi
  mkdir -p "${HOME}/Library/LaunchAgents"
  mkdir -p "${LOG_DIR}"
}

write_plist() {
  cat > "${PLIST_PATH}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${PROJECT_ROOT}/dashboard.py</string>
    <string>--host</string>
    <string>127.0.0.1</string>
    <string>--port</string>
    <string>8000</string>
  </array>

  <key>WorkingDirectory</key>
  <string>${PROJECT_ROOT}</string>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>${OUT_LOG}</string>

  <key>StandardErrorPath</key>
  <string>${ERR_LOG}</string>
</dict>
</plist>
EOF
}

is_loaded() {
  launchctl print "${DOMAIN}/${LABEL}" >/dev/null 2>&1
}

stop_existing_port_8000() {
  local pids
  pids="$(lsof -ti tcp:8000 -sTCP:LISTEN || true)"
  if [[ -n "${pids}" ]]; then
    kill ${pids} >/dev/null 2>&1 || true
    sleep 1
    pids="$(lsof -ti tcp:8000 -sTCP:LISTEN || true)"
    if [[ -n "${pids}" ]]; then
      kill -9 ${pids} >/dev/null 2>&1 || true
    fi
  fi
}

install_service() {
  ensure_prereqs
  write_plist
  stop_existing_port_8000
  launchctl bootout "${DOMAIN}/${LABEL}" >/dev/null 2>&1 || true
  launchctl bootstrap "${DOMAIN}" "${PLIST_PATH}"
  launchctl enable "${DOMAIN}/${LABEL}" >/dev/null 2>&1 || true
  launchctl kickstart -k "${DOMAIN}/${LABEL}"
  echo "Installed and started ${LABEL}"
}

start_service() {
  ensure_prereqs
  if [[ ! -f "${PLIST_PATH}" ]]; then
    install_service
    return
  fi
  stop_existing_port_8000
  if ! is_loaded; then
    launchctl bootstrap "${DOMAIN}" "${PLIST_PATH}"
  fi
  launchctl kickstart -k "${DOMAIN}/${LABEL}"
  echo "Started ${LABEL}"
}

stop_service() {
  launchctl bootout "${DOMAIN}/${LABEL}" >/dev/null 2>&1 || true
  echo "Stopped ${LABEL}"
}

status_service() {
  if is_loaded; then
    echo "Service loaded: ${LABEL}"
    launchctl print "${DOMAIN}/${LABEL}" | rg -n "state =|pid =|last exit code =|path =|program =" || true
  else
    echo "Service not loaded: ${LABEL}"
    exit 1
  fi
}

logs_service() {
  mkdir -p "${LOG_DIR}"
  echo "--- ${OUT_LOG} ---"
  tail -n 80 "${OUT_LOG}" 2>/dev/null || true
  echo "--- ${ERR_LOG} ---"
  tail -n 80 "${ERR_LOG}" 2>/dev/null || true
}

uninstall_service() {
  launchctl bootout "${DOMAIN}/${LABEL}" >/dev/null 2>&1 || true
  rm -f "${PLIST_PATH}"
  echo "Uninstalled ${LABEL}"
}

cmd="${1:-}"
case "${cmd}" in
  install) install_service ;;
  start) start_service ;;
  stop) stop_service ;;
  restart) stop_service; start_service ;;
  status) status_service ;;
  logs) logs_service ;;
  uninstall) uninstall_service ;;
  *) usage; exit 1 ;;
esac

