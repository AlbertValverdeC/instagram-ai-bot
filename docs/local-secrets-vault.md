# Secrets Vault (Local, cifrado con contraseña maestra)

Este proyecto incluye un vault local cifrado para guardar API keys/tokens sin dejarlos en `.env` en texto plano.

## Ubicación del vault

- Archivo cifrado: `~/.config/instagram-ai-bot/secrets.vault.json`
- Permisos: `600` (solo tu usuario local)

## 1) Migrar claves desde `.env` al vault

```bash
.venv/bin/python scripts/secrets_vault.py migrate
```

- Te pedirá una contraseña maestra.
- Detecta y migra automáticamente keys/tokens sensibles.
- Por defecto **redacta** esas claves en `.env` (y crea backup automático `.env.backup-YYYYMMDD-HHMMSS`).

## 2) Ver qué claves hay en el vault (sin mostrar valores)

```bash
.venv/bin/python scripts/secrets_vault.py list
```

## 3) Ejecutar comandos cargando secretos desde el vault

```bash
scripts/with_secrets.sh <comando>
```

Ejemplos:

```bash
scripts/with_secrets.sh .venv/bin/python dashboard.py --host 127.0.0.1 --port 8000
scripts/with_secrets.sh .venv/bin/python main_pipeline.py --dry-run
```

Atajo para dashboard local:

```bash
scripts/start_dashboard_secure.sh
```

## Nota importante

- Si ejecutas el proyecto **sin** `with_secrets.sh` (o sin exportar vars manualmente), no tendrá acceso a los secretos migrados.
- El endpoint de UI que guarda keys (`/api/keys`) sigue escribiendo en `.env`; usa el vault como fuente principal de secretos.
