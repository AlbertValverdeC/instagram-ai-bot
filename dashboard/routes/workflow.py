from __future__ import annotations

import json

from flask import Blueprint, jsonify, request

from config.settings import OPENAI_API_KEY
from dashboard.auth import require_api_token
from dashboard.config import DATA_DIR
from dashboard.services.pipeline_runner import is_running

try:
    from modules.carousel_designer import create as create_slides
    from modules.content_generator import generate as generate_content
    from modules.content_generator import generate_text_proposals
    from modules.engagement import get_strategy
    from modules.post_store import create_draft_post, ensure_schema as ensure_post_store_schema
    from modules.researcher import find_trending_topic, find_trending_topics
except Exception:
    create_slides = None
    generate_content = None
    generate_text_proposals = None
    get_strategy = None
    create_draft_post = None
    ensure_post_store_schema = None
    find_trending_topic = None
    find_trending_topics = None

bp = Blueprint("workflow_routes", __name__)


def _require_modules(required: dict[str, object]):
    missing = [name for name, ref in required.items() if ref is None]
    if missing:
        return jsonify({"error": f"Módulos de workflow no disponibles: {', '.join(missing)}"}), 500
    return None


def _ensure_openai_key():
    if OPENAI_API_KEY:
        return None
    return jsonify({"error": "OPENAI_API_KEY no está configurada."}), 400


def _safe_save_json(path, payload: dict | list):
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _topic_to_proposal(topic: dict, idx: int) -> dict:
    """Convert a topic dict into a proposal card for the frontend."""
    title = topic.get("topic", "")
    why = topic.get("why", "")
    virality = topic.get("virality_score", 7)
    key_points = topic.get("key_points", [])
    # Build a short preview from the first 2 key points
    preview_points = [str(kp) for kp in key_points[:2] if str(kp).strip()]
    caption_preview = " ".join(preview_points)[:280] if preview_points else why[:280]

    return {
        "id": f"p{idx}",
        "angle": title,
        "hook": why or title,
        "caption_preview": caption_preview,
        "cta": "¿Qué opinas? Te leo en comentarios.",
        "virality_score": virality,
    }


@bp.post("/api/proposals")
def api_generate_proposals():
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    deps_error = _require_modules(
        {
            "find_trending_topics": find_trending_topics,
        }
    )
    if deps_error:
        return deps_error

    key_error = _ensure_openai_key()
    if key_error:
        return key_error

    if is_running():
        return jsonify({"error": "Hay un pipeline en ejecución. Espera a que termine."}), 409

    data = request.get_json(silent=True) or {}
    focus_topic = str(data.get("topic") or "").strip() or None
    requested_count = data.get("count", 3)
    try:
        count = max(1, min(int(requested_count), 5))
    except Exception:
        count = 3

    try:
        # Get N different topics (each proposal = different story)
        topics = find_trending_topics(focus_topic=focus_topic, count=count)

        # Convert each topic to a proposal card
        proposals = [_topic_to_proposal(t, i + 1) for i, t in enumerate(topics)]

        # Save first topic as last_topic for dedup, all topics for reference
        if topics:
            _safe_save_json(DATA_DIR / "last_topic.json", topics[0])
        _safe_save_json(DATA_DIR / "last_proposals.json", proposals)
        _safe_save_json(DATA_DIR / "last_topics.json", topics)

        # Return the first topic as primary (for backwards compat) + all topics
        return jsonify({
            "topic": topics[0] if topics else {},
            "topics": topics,
            "proposals": proposals,
        })
    except Exception as e:
        return jsonify({"error": f"No se pudieron generar propuestas: {e}"}), 500


@bp.post("/api/drafts")
def api_create_draft():
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    deps_error = _require_modules(
        {
            "generate_content": generate_content,
            "create_slides": create_slides,
            "get_strategy": get_strategy,
            "create_draft_post": create_draft_post,
            "ensure_post_store_schema": ensure_post_store_schema,
        }
    )
    if deps_error:
        return deps_error

    key_error = _ensure_openai_key()
    if key_error:
        return key_error

    if is_running():
        return jsonify({"error": "Hay un pipeline en ejecución. Espera a que termine."}), 409

    data = request.get_json(silent=True) or {}
    topic = data.get("topic")
    proposal = data.get("proposal")
    if not isinstance(topic, dict):
        return jsonify({"error": "Payload inválido: falta topic"}), 400
    if not isinstance(proposal, dict):
        return jsonify({"error": "Payload inválido: falta proposal"}), 400

    template = data.get("template")
    if template is not None:
        try:
            template = int(template)
        except Exception:
            return jsonify({"error": "template debe ser entero"}), 400

    try:
        ensure_post_store_schema()
        content = generate_content(topic, proposal=proposal)
        strategy = get_strategy(topic, content)
        image_paths = create_slides(content, template_index=template, topic=topic)
        post_id = create_draft_post(
            topic=topic,
            proposal=proposal,
            content=content,
            strategy=strategy,
        )

        _safe_save_json(DATA_DIR / "last_topic.json", topic)
        _safe_save_json(DATA_DIR / "last_content.json", content)

        return jsonify(
            {
                "post_id": post_id,
                "status": "draft",
                "topic": topic,
                "proposal": proposal,
                "content": content,
                "strategy": strategy,
                "slides": [p.name for p in image_paths],
            }
        )
    except Exception as e:
        return jsonify({"error": f"No se pudo crear draft: {e}"}), 500
