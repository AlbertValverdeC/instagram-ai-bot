# Deploy sin depender del Mac (Cloud Run)

Este flujo te deja el bot corriendo en Google Cloud, con ejecución diaria automática.

## 1) Prerrequisitos (una vez)

1. Instala y autentica `gcloud`.
2. Configura proyecto:
   - `gcloud config set project TU_PROJECT_ID`
3. Ten el `.env` completo en este repo (API keys + Meta token).

## 2) Deploy del dashboard en Cloud Run

Desde la raíz del proyecto:

```bash
chmod +x scripts/cloud/deploy_cloud_run.sh scripts/cloud/setup_scheduler.sh
PROJECT_ID=tu-project-id REGION=europe-west1 scripts/cloud/deploy_cloud_run.sh
```

Qué hace:

- Construye imagen Docker y la sube.
- Despliega servicio `techtokio-dashboard` (o el nombre que pongas).
- Carga variables desde `.env`.
- Genera `DASHBOARD_API_TOKEN` si no existe.
- Fuerza `PUBLIC_IMAGE_BASE_URL` a la URL real del servicio Cloud Run.

## 3) Programar ejecución diaria (`mode=live`)

```bash
PROJECT_ID=tu-project-id REGION=europe-west1 \
SCHEDULE="30 8 * * *" TIMEZONE="Europe/Madrid" \
scripts/cloud/setup_scheduler.sh
```

Eso crea/actualiza un Cloud Scheduler job que llama:

- `POST /api/run`
- body: `{"mode":"live"}`
- header: `X-API-Token: DASHBOARD_API_TOKEN`

## 4) Lanzar una ejecución manual de prueba

```bash
gcloud scheduler jobs run techtokio-live-daily --location europe-west1
```

## 5) Variables importantes en `.env`

- `OPENAI_API_KEY`
- `GOOGLE_AI_API_KEY`
- `TAVILY_API_KEY`
- `INSTAGRAM_ACCOUNT_ID`
- `META_ACCESS_TOKEN`
- `GRAPH_API_VERSION=v25.0`
- `PUBLIC_IMAGE_BASE_URL` (si publicas con URLs propias)
- `DASHBOARD_API_TOKEN` (seguridad endpoints POST)
- `DATABASE_URL` (obligatorio PostgreSQL en cloud si quieres persistencia real)
- `DUPLICATE_TOPIC_WINDOW_DAYS` (ventana para bloquear temas repetidos)

## 6) Activar PostgreSQL persistente (recomendado)

Si `DATABASE_URL` empieza por `sqlite://`, en Cloud Run perderás historial/métricas al redeploy o reinicio.

### Opción rápida (Supabase/Neon/Cloud SQL Postgres)

1. Crea una base PostgreSQL.
2. Copia la URL en formato SQLAlchemy:

```bash
postgresql+psycopg://USER:PASS@HOST:5432/DBNAME?sslmode=require
```

3. En tu `.env`, define:

```bash
DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/DBNAME?sslmode=require
```

Si usas Cloud SQL con socket Unix (recomendado en Cloud Run):

```bash
CLOUD_SQL_INSTANCE_CONNECTION_NAME=tu-proyecto:europe-west1:techtokio-pg
DATABASE_URL=postgresql+psycopg://USER:PASS@/DBNAME?host=/cloudsql/tu-proyecto:europe-west1:techtokio-pg
```

4. Redeploy:

```bash
PROJECT_ID=tu-project-id REGION=europe-west1 scripts/cloud/deploy_cloud_run.sh
```

5. (Opcional) Migrar histórico local `history.json` a la DB:

```bash
.venv/bin/python scripts/db/migrate_history_to_db.py
```

El dashboard ahora tiene:
- `GET /api/db-status` para ver si la DB es persistente.
- `POST /api/posts/sync-metrics` para traer métricas de IG a la DB.

## Notas

- El servicio queda online 24/7 sin usar tu PC.
- Si cambias claves/tokens, vuelve a ejecutar `deploy_cloud_run.sh`.
- Seguridad dashboard: si `DASHBOARD_API_TOKEN` está definido, todas las rutas `/api/*` requieren header `X-API-Token`.
- En la UI web, configura el token en la esquina superior derecha (`API token dashboard`) para operar el panel.
- En Cloud Run el pipeline se ejecuta en modo síncrono por defecto para evitar que se corte en background.
- Si en la tarjeta "Publicaciones (DB)" ves warning de SQLite, estás en modo no persistente.
