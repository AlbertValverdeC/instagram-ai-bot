from __future__ import annotations

from flask import Blueprint, jsonify, request

from dashboard.auth import require_api_token
from dashboard.config import API_KEYS_CONFIG
from dashboard.services.env_manager import mask_value, read_env, write_env

bp = Blueprint("keys_routes", __name__)


@bp.get("/api/keys")
def api_keys_get():
    """Return all API keys (masked) with their config metadata."""
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    env = read_env()
    keys = []
    for cfg in API_KEYS_CONFIG:
        is_secret = cfg.get("secret", True)
        raw = env.get(cfg["key"], "")
        keys.append(
            {
                "key": cfg["key"],
                "label": cfg["label"],
                "hint": cfg["hint"],
                "placeholder": cfg["placeholder"],
                "required": cfg["required"],
                "group": cfg["group"],
                "url": cfg.get("url"),
                "secret": is_secret,
                "value": mask_value(raw, is_secret) if is_secret else raw,
                "configured": bool(raw and raw != cfg["placeholder"] and not raw.startswith("xxxxxxx")),
            }
        )
    return jsonify(keys)


@bp.post("/api/keys")
def api_keys_save():
    """Save API keys to .env file."""
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "No data"}), 400

    env = read_env()
    updates = {}
    for k, v in data.items():
        if v and v.startswith("***"):
            continue
        updates[k] = v

    if updates:
        _ = {**env, **updates}
        write_env(updates)

    return jsonify({"saved": len(updates)})
