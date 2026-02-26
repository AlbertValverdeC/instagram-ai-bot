from __future__ import annotations

import copy
import json

from flask import Blueprint, jsonify, request

from dashboard.auth import require_api_token
from dashboard.config import DEFAULT_RESEARCH_CONFIG, RESEARCH_CONFIG_FILE

bp = Blueprint("research_routes", __name__)


@bp.get("/api/research-config")
def api_research_config_get():
    """Return current research config (custom or defaults)."""
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    config = copy.deepcopy(DEFAULT_RESEARCH_CONFIG)
    is_custom = RESEARCH_CONFIG_FILE.exists()
    if is_custom:
        try:
            custom = json.loads(RESEARCH_CONFIG_FILE.read_text(encoding="utf-8"))
            for key in config:
                if key in custom:
                    config[key] = custom[key]
        except Exception:
            is_custom = False
    return jsonify({"config": config, "custom": is_custom, "defaults": DEFAULT_RESEARCH_CONFIG})


@bp.post("/api/research-config")
def api_research_config_save():
    """Save research config to JSON file."""
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    config = data.get("config")
    if not config:
        return jsonify({"error": "Falta campo: config"}), 400

    for key in ["subreddits", "rss_feeds", "trends_keywords"]:
        if key in config and not isinstance(config[key], list):
            return jsonify({"error": f"{key} debe ser una lista"}), 400
        if key in config and len(config[key]) == 0:
            return jsonify({"error": f"{key} no puede estar vacio"}), 400

    if "newsapi_domains" in config and not isinstance(config["newsapi_domains"], str):
        return jsonify({"error": "newsapi_domains debe ser texto (dominios separados por coma)"}), 400

    RESEARCH_CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return jsonify({"saved": True})


@bp.post("/api/research-config/reset")
def api_research_config_reset():
    """Reset research config to defaults (delete the JSON file)."""
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    if RESEARCH_CONFIG_FILE.exists():
        RESEARCH_CONFIG_FILE.unlink()
    return jsonify({"reset": True})
