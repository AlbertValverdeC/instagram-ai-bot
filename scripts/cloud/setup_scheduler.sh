#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

SERVICE_NAME="${SERVICE_NAME:-techtokio-dashboard}"
REGION="${REGION:-europe-west1}"
SCHEDULER_LOCATION="${SCHEDULER_LOCATION:-${REGION}}"
JOB_NAME="${JOB_NAME:-techtokio-live-daily}"
SCHEDULE="${SCHEDULE:-30 8 * * *}"
TIMEZONE="${TIMEZONE:-Europe/Madrid}"
MODE="${MODE:-live}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Error: PROJECT_ID no definido."
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Error: no existe ${ENV_FILE}"
  exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "Error: gcloud no está instalado."
  exit 1
fi

get_env_value() {
  local key="$1"
  python3 - "$ENV_FILE" "$key" <<'PY'
import sys
env_file, key = sys.argv[1], sys.argv[2]
value = ""
with open(env_file, encoding="utf-8") as f:
    for raw in f:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            value = v.strip()
print(value)
PY
}

token="$(get_env_value DASHBOARD_API_TOKEN)"
if [[ -z "${token}" ]]; then
  echo "Error: DASHBOARD_API_TOKEN vacío en .env. Ejecuta primero deploy_cloud_run.sh"
  exit 1
fi

gcloud config set project "${PROJECT_ID}" >/dev/null
gcloud services enable cloudscheduler.googleapis.com run.googleapis.com >/dev/null

service_url="$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format='value(status.url)')"
if [[ -z "${service_url}" ]]; then
  echo "Error: no pude obtener URL del servicio ${SERVICE_NAME}."
  exit 1
fi

uri="${service_url}/api/run"
headers="Content-Type=application/json,X-API-Token=${token}"
body="{\"mode\":\"${MODE}\"}"

if gcloud scheduler jobs describe "${JOB_NAME}" --location "${SCHEDULER_LOCATION}" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "${JOB_NAME}" \
    --location "${SCHEDULER_LOCATION}" \
    --schedule "${SCHEDULE}" \
    --time-zone "${TIMEZONE}" \
    --uri "${uri}" \
    --http-method POST \
    --headers "${headers}" \
    --message-body "${body}"
  action="updated"
else
  gcloud scheduler jobs create http "${JOB_NAME}" \
    --location "${SCHEDULER_LOCATION}" \
    --schedule "${SCHEDULE}" \
    --time-zone "${TIMEZONE}" \
    --uri "${uri}" \
    --http-method POST \
    --headers "${headers}" \
    --message-body "${body}"
  action="created"
fi

echo
echo "Scheduler ${action}: ${JOB_NAME}"
echo "Cron: ${SCHEDULE} (${TIMEZONE})"
echo "Target: ${uri}"
echo
echo "Para probar ahora: gcloud scheduler jobs run ${JOB_NAME} --location ${SCHEDULER_LOCATION}"
