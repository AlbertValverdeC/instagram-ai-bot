#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

SERVICE_NAME="${SERVICE_NAME:-techtokio-dashboard}"
REGION="${REGION:-europe-west1}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Error: PROJECT_ID no definido. Exporta PROJECT_ID o configura gcloud."
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

upsert_env() {
  local key="$1"
  local val="$2"
  python3 - "${ENV_FILE}" "${key}" "${val}" <<'PY'
import pathlib
import sys

env_path = pathlib.Path(sys.argv[1])
key = sys.argv[2]
val = sys.argv[3]

lines = []
found = False
if env_path.exists():
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k = line.split("=", 1)[0].strip()
            if k == key:
                lines.append(f"{key}={val}")
                found = True
                continue
        lines.append(raw)

if not found:
    lines.append(f"{key}={val}")

env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

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

# Recommended defaults for Cloud Run
upsert_env HOST "0.0.0.0"
upsert_env PORT "8080"

token="$(get_env_value DASHBOARD_API_TOKEN)"
if [[ -z "${token}" ]]; then
  token="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"
  upsert_env DASHBOARD_API_TOKEN "${token}"
  echo "Se generó DASHBOARD_API_TOKEN automáticamente en .env"
fi

tmp_env_yaml="$(mktemp)"
trap 'rm -f "${tmp_env_yaml}"' EXIT

python3 - "${ENV_FILE}" "${tmp_env_yaml}" <<'PY'
import json
import sys

env_file, out_file = sys.argv[1], sys.argv[2]
items = {}
with open(env_file, encoding="utf-8") as f:
    for raw in f:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k:
            items[k] = v

with open(out_file, "w", encoding="utf-8") as out:
    for k in sorted(items.keys()):
        out.write(f"{k}: {json.dumps(items[k], ensure_ascii=False)}\n")
PY

IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:$(date +%Y%m%d-%H%M%S)"

echo "Proyecto: ${PROJECT_ID}"
echo "Región:   ${REGION}"
echo "Servicio: ${SERVICE_NAME}"
echo "Imagen:   ${IMAGE}"

gcloud config set project "${PROJECT_ID}" >/dev/null
gcloud services enable run.googleapis.com cloudbuild.googleapis.com cloudscheduler.googleapis.com >/dev/null

gcloud builds submit "${PROJECT_ROOT}" --tag "${IMAGE}"

gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --cpu 1 \
  --memory 2Gi \
  --timeout 3600 \
  --max-instances 1 \
  --env-vars-file "${tmp_env_yaml}"

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format='value(status.url)')"

echo
echo "Deploy completado."
echo "URL: ${SERVICE_URL}"
echo "Token dashboard (guárdalo): ${token}"
echo
echo "Siguiente paso: scripts/cloud/setup_scheduler.sh"
