#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

usage() {
  cat <<'EOF'
Uso:
  scripts/ig_publish_once.sh --image-url "https://..." --caption "Texto"
  scripts/ig_publish_once.sh --image-file "/ruta/local/imagen.jpg" --caption "Texto"

Notas:
  - Lee INSTAGRAM_ACCOUNT_ID, META_ACCESS_TOKEN, GRAPH_API_VERSION y PUBLIC_IMAGE_BASE_URL desde .env
  - Si usas --image-file, requiere PUBLIC_IMAGE_BASE_URL para construir la URL pública.
EOF
}

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Error: no existe ${ENV_FILE}"
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

GRAPH_API_VERSION="${GRAPH_API_VERSION:-v25.0}"
if [[ "${GRAPH_API_VERSION}" != v* ]]; then
  GRAPH_API_VERSION="v${GRAPH_API_VERSION}"
fi
GRAPH_API_BASE="https://graph.facebook.com/${GRAPH_API_VERSION}"

IMAGE_URL=""
IMAGE_FILE=""
CAPTION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image-url)
      IMAGE_URL="${2:-}"
      shift 2
      ;;
    --image-file)
      IMAGE_FILE="${2:-}"
      shift 2
      ;;
    --caption)
      CAPTION="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Parámetro no reconocido: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${INSTAGRAM_ACCOUNT_ID:-}" || -z "${META_ACCESS_TOKEN:-}" ]]; then
  echo "Error: faltan INSTAGRAM_ACCOUNT_ID o META_ACCESS_TOKEN en .env"
  exit 1
fi

if [[ -n "${IMAGE_FILE}" && -n "${IMAGE_URL}" ]]; then
  echo "Error: usa solo --image-url o --image-file, no ambos."
  exit 1
fi

if [[ -z "${IMAGE_FILE}" && -z "${IMAGE_URL}" ]]; then
  echo "Error: debes indicar --image-url o --image-file."
  exit 1
fi

if [[ -z "${CAPTION}" ]]; then
  echo "Error: falta --caption."
  exit 1
fi

if [[ -n "${IMAGE_FILE}" ]]; then
  if [[ -z "${PUBLIC_IMAGE_BASE_URL:-}" ]]; then
    echo "Error: para --image-file necesitas PUBLIC_IMAGE_BASE_URL en .env"
    exit 1
  fi
  file_name="$(basename "${IMAGE_FILE}")"
  base="${PUBLIC_IMAGE_BASE_URL%/}"
  IMAGE_URL="${base}/${file_name}"
fi

headers="$(curl -sS -L -I "${IMAGE_URL}" || true)"
status="$(printf '%s\n' "${headers}" | awk '/^HTTP/{code=$2} END{print code}')"
ctype="$(printf '%s\n' "${headers}" | awk 'BEGIN{IGNORECASE=1} /^content-type:/{print tolower($2)}' | tr -d '\r' | tail -n1)"

if [[ "${status}" != "200" ]]; then
  echo "Error: image_url no devuelve 200 (${status:-sin_status}) -> ${IMAGE_URL}"
  exit 1
fi
if [[ "${ctype}" != image/* ]]; then
  echo "Error: image_url no parece imagen (Content-Type=${ctype:-missing}) -> ${IMAGE_URL}"
  exit 1
fi

echo "OK URL pública: ${IMAGE_URL}"
echo "Creando contenedor..."

create_resp="$(curl -sS -X POST "${GRAPH_API_BASE}/${INSTAGRAM_ACCOUNT_ID}/media" \
  -d "image_url=${IMAGE_URL}" \
  --data-urlencode "caption=${CAPTION}" \
  -d "access_token=${META_ACCESS_TOKEN}")"

CREATION_ID="$(printf '%s' "${create_resp}" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("id",""))' 2>/dev/null || true)"
if [[ -z "${CREATION_ID}" ]]; then
  echo "Error creando contenedor:"
  echo "${create_resp}"
  exit 1
fi

echo "CREATION_ID=${CREATION_ID}"
echo "Publicando..."

publish_resp="$(curl -sS -X POST "${GRAPH_API_BASE}/${INSTAGRAM_ACCOUNT_ID}/media_publish" \
  -d "creation_id=${CREATION_ID}" \
  -d "access_token=${META_ACCESS_TOKEN}")"

MEDIA_ID="$(printf '%s' "${publish_resp}" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("id",""))' 2>/dev/null || true)"
if [[ -z "${MEDIA_ID}" ]]; then
  echo "Error publicando:"
  echo "${publish_resp}"
  exit 1
fi

echo "MEDIA_ID=${MEDIA_ID}"
echo "Consultando permalink..."

curl -sS "${GRAPH_API_BASE}/${MEDIA_ID}?fields=id,media_type,permalink,timestamp&access_token=${META_ACCESS_TOKEN}"
echo
