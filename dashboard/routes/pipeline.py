from __future__ import annotations

import json
from datetime import UTC, datetime

from flask import Blueprint, jsonify, request

from dashboard.auth import require_api_token
from dashboard.config import DATA_DIR, OUTPUT_DIR
from dashboard.services.pipeline_runner import (
    get_state_snapshot,
    is_running,
    maybe_auto_sync_instagram,
    pipeline_execution_mode,
    run_pipeline_sync,
    run_pipeline_thread,
    set_running,
)

bp = Blueprint("pipeline_routes", __name__)


def _workspace_files():
    return [
        DATA_DIR / "last_topic.json",
        DATA_DIR / "last_content.json",
        DATA_DIR / "last_proposals.json",
        DATA_DIR / "last_topics.json",
    ]


def _workspace_slide_paths():
    return sorted(
        list(OUTPUT_DIR.glob("slide_*.jpg")) + list(OUTPUT_DIR.glob("slide_*.png")),
        key=lambda p: p.name,
    )


def _clear_workspace() -> tuple[list[str], int]:
    cleared_files: list[str] = []
    cleared_slides = 0

    for path in _workspace_files():
        try:
            if path.exists():
                path.unlink()
                cleared_files.append(path.name)
        except Exception:
            pass

    for path in _workspace_slide_paths():
        try:
            path.unlink(missing_ok=True)
            cleared_slides += 1
        except Exception:
            pass

    return cleared_files, cleared_slides


@bp.get("/api/state")
def api_state():
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    maybe_auto_sync_instagram()

    topic = None
    topic_file = DATA_DIR / "last_topic.json"
    if topic_file.exists():
        with open(topic_file, encoding="utf-8") as f:
            topic = json.load(f)

    content = None
    content_file = DATA_DIR / "last_content.json"
    if content_file.exists():
        with open(content_file, encoding="utf-8") as f:
            content = json.load(f)

    proposals = []
    proposals_file = DATA_DIR / "last_proposals.json"
    if proposals_file.exists():
        with open(proposals_file, encoding="utf-8") as f:
            loaded = json.load(f)
            if isinstance(loaded, list):
                proposals = loaded

    slide_paths = _workspace_slide_paths()
    slides = sorted(f.name for f in slide_paths)

    history = []
    history_file = DATA_DIR / "history.json"
    if history_file.exists():
        with open(history_file, encoding="utf-8") as f:
            history = json.load(f)

    mtimes: list[float] = []
    for path in _workspace_files():
        try:
            if path.exists():
                mtimes.append(path.stat().st_mtime)
        except Exception:
            pass
    for path in slide_paths:
        try:
            mtimes.append(path.stat().st_mtime)
        except Exception:
            pass

    workspace_updated_at = None
    if mtimes:
        workspace_updated_at = (
            datetime.fromtimestamp(max(mtimes), tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        )

    return jsonify(
        {
            "topic": topic,
            "content": content,
            "proposals": proposals,
            "slides": slides,
            "workspace_has_data": bool(topic or content or proposals or slides),
            "workspace_updated_at": workspace_updated_at,
            "history_count": len(history),
        }
    )


@bp.post("/api/workspace/clear")
def api_workspace_clear():
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    cleared_files, cleared_slides = _clear_workspace()
    return jsonify(
        {
            "ok": True,
            "cleared_files": cleared_files,
            "cleared_slides": cleared_slides,
        }
    )


@bp.post("/api/run")
def api_run():
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    if is_running():
        return jsonify({"error": "Pipeline already running"}), 409

    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "test")
    if mode not in ("test", "dry-run", "live"):
        return jsonify({"error": f"Invalid mode: {mode}"}), 400

    template = data.get("template")
    if template is not None:
        template = int(template)

    topic = (data.get("topic") or "").strip() or None

    set_running(mode if not topic else f"{mode} (topic: {topic})")

    if pipeline_execution_mode() == "sync":
        result = run_pipeline_sync(mode, template, topic)
        return jsonify(result), 200 if result["status"] == "done" else 500

    run_pipeline_thread(mode, template, topic)
    return jsonify({"status": "started", "mode": mode})


@bp.post("/api/search-topic")
def api_search_topic():
    """Run only the research step for a user-provided topic."""
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    if is_running():
        return jsonify({"error": "Pipeline already running"}), 409

    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "Debes escribir un tema"}), 400

    set_running(f"research-only (topic: {topic})")

    if pipeline_execution_mode() == "sync":
        result = run_pipeline_sync("dry-run", None, topic, "research")
        response = {
            "status": result["status"],
            "mode": "research-only",
            "topic": topic,
            "elapsed": result["elapsed"],
            "error_summary": result["error_summary"],
            "output_tail": result["output_tail"],
        }
        return jsonify(response), 200 if result["status"] == "done" else 500

    run_pipeline_thread("dry-run", None, topic, "research")
    return jsonify({"status": "started", "mode": "research-only", "topic": topic})


@bp.get("/api/status")
def api_status():
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    maybe_auto_sync_instagram()

    return jsonify(get_state_snapshot())
