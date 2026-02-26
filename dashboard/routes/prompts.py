from __future__ import annotations

from flask import Blueprint, jsonify, request

from dashboard.auth import require_api_token
from dashboard.config import PROMPTS_CONFIG, PROMPTS_DIR

bp = Blueprint("prompts_routes", __name__)


def _get_prompt_defaults() -> dict:
    """Lazy-import all default prompts from modules."""
    from modules.prompt_director import (
        _DEFAULT_CONTENT_META,
        _DEFAULT_IMAGE_META,
        _DEFAULT_RESEARCH_META,
    )
    from modules.researcher import _DEFAULT_RESEARCH_FALLBACK
    from modules.content_generator import _DEFAULT_CONTENT_FALLBACK
    from modules.image_generator import _DEFAULT_IMAGE_FALLBACK

    return {
        "research_meta": _DEFAULT_RESEARCH_META,
        "research_fallback": _DEFAULT_RESEARCH_FALLBACK,
        "content_meta": _DEFAULT_CONTENT_META,
        "content_fallback": _DEFAULT_CONTENT_FALLBACK,
        "image_meta": _DEFAULT_IMAGE_META,
        "image_fallback": _DEFAULT_IMAGE_FALLBACK,
    }


@bp.get("/api/prompts")
def api_prompts_get():
    """Return all 6 prompts with metadata, current text, and custom flag."""
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    defaults = _get_prompt_defaults()
    result = []
    for cfg in PROMPTS_CONFIG:
        pid = cfg["id"]
        custom_file = PROMPTS_DIR / f"{pid}.txt"
        is_custom = custom_file.exists()
        if is_custom:
            text = custom_file.read_text(encoding="utf-8")
        else:
            text = defaults.get(pid, "")
        result.append(
            {
                **cfg,
                "text": text,
                "default_text": defaults.get(pid, ""),
                "custom": is_custom,
            }
        )
    return jsonify(result)


@bp.post("/api/prompts")
def api_prompts_save():
    """Save a custom prompt. Validates that required {variables} are present."""
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    pid = data.get("id", "")
    text = data.get("text", "")

    if not pid or not text:
        return jsonify({"error": "Faltan campos: id, text"}), 400

    cfg = next((c for c in PROMPTS_CONFIG if c["id"] == pid), None)
    if cfg is None:
        return jsonify({"error": f"Prompt desconocido: {pid}"}), 400

    missing = []
    for var in cfg["variables"]:
        placeholder = "{" + var + "}"
        if placeholder not in text:
            missing.append(placeholder)

    if missing:
        return (
            jsonify(
                {
                    "error": f"Variables requeridas no encontradas: {', '.join(missing)}",
                    "missing": missing,
                }
            ),
            400,
        )

    filepath = PROMPTS_DIR / f"{pid}.txt"
    filepath.write_text(text, encoding="utf-8")
    return jsonify({"saved": pid})


@bp.post("/api/prompts/reset")
def api_prompts_reset():
    """Reset a prompt to its default (delete the custom .txt file)."""
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    pid = data.get("id", "")

    if not pid:
        return jsonify({"error": "Falta campo: id"}), 400

    cfg = next((c for c in PROMPTS_CONFIG if c["id"] == pid), None)
    if cfg is None:
        return jsonify({"error": f"Prompt desconocido: {pid}"}), 400

    filepath = PROMPTS_DIR / f"{pid}.txt"
    if filepath.exists():
        filepath.unlink()

    return jsonify({"reset": pid})
