from __future__ import annotations

from flask import Flask, abort, send_from_directory

from dashboard.config import (
    DOCS_FILE,
    FRONTEND_DIST_DIR,
    FRONTEND_INDEX_FILE,
    OUTPUT_DIR,
    ensure_dirs,
)
from dashboard.config import (
    PROJECT_ROOT as PROJECT_ROOT,
)
from dashboard.routes import register_blueprints
from dashboard.services.scheduler import start_scheduler_daemon


def create_app() -> Flask:
    app = Flask(__name__)
    ensure_dirs()

    register_blueprints(app)
    start_scheduler_daemon(app)

    @app.after_request
    def add_cors_headers(response):
        response.headers.setdefault("Access-Control-Allow-Origin", "*")
        response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Token")
        response.headers.setdefault("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        return response

    @app.route("/slides/<path:filename>")
    def serve_slide(filename: str):
        return send_from_directory(str(OUTPUT_DIR), filename)

    @app.route("/docs")
    def docs():
        if DOCS_FILE.exists():
            return DOCS_FILE.read_text(encoding="utf-8")
        return "Docs not found", 404

    @app.route("/")
    def dashboard_index():
        if FRONTEND_INDEX_FILE.exists():
            return FRONTEND_INDEX_FILE.read_text(encoding="utf-8")
        return (
            "Frontend no construido. Ejecuta: cd frontend && npm install && npm run build",
            503,
        )

    @app.route("/<path:path>")
    def frontend_static(path: str):
        if path.startswith("api/") or path.startswith("slides/") or path == "docs":
            abort(404)

        candidate = FRONTEND_DIST_DIR / path
        if candidate.exists() and candidate.is_file():
            return send_from_directory(str(FRONTEND_DIST_DIR), path)

        if FRONTEND_INDEX_FILE.exists():
            return FRONTEND_INDEX_FILE.read_text(encoding="utf-8")

        abort(404)

    return app


# Module-level app instance for gunicorn (e.g. `gunicorn dashboard:app`)
app = create_app()
