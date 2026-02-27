from __future__ import annotations

import json

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

    slides = sorted(f.name for f in list(OUTPUT_DIR.glob("slide_*.jpg")) + list(OUTPUT_DIR.glob("slide_*.png")))

    history = []
    history_file = DATA_DIR / "history.json"
    if history_file.exists():
        with open(history_file, encoding="utf-8") as f:
            history = json.load(f)

    return jsonify(
        {
            "topic": topic,
            "content": content,
            "proposals": proposals,
            "slides": slides,
            "history_count": len(history),
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
