from __future__ import annotations

from flask import Blueprint, jsonify, request

from dashboard.auth import require_api_token
from dashboard.config import OUTPUT_DIR
from dashboard.services.pipeline_runner import (
    classify_publish_error_text,
    get_auto_sync_interval_minutes,
    is_running,
)

try:
    from modules.post_store import (
        RETRYABLE_STATUSES,
        ensure_schema as ensure_post_store_schema,
        get_db_runtime_info as get_post_store_db_runtime_info,
        get_post as db_get_post,
        list_posts as db_list_posts,
        mark_post_publish_attempt as db_mark_post_publish_attempt,
        mark_post_publish_error as db_mark_post_publish_error,
        mark_post_published as db_mark_post_published,
    )
except Exception:
    RETRYABLE_STATUSES = {"generated", "publish_error"}
    ensure_post_store_schema = None
    get_post_store_db_runtime_info = None
    db_get_post = None
    db_list_posts = None
    db_mark_post_publish_attempt = None
    db_mark_post_publish_error = None
    db_mark_post_published = None

try:
    from modules.metrics_sync import (
        reconcile_pending_posts_with_instagram as db_reconcile_pending_posts,
    )
    from modules.metrics_sync import sync_recent_post_metrics as db_sync_post_metrics
except Exception:
    db_sync_post_metrics = None
    db_reconcile_pending_posts = None

bp = Blueprint("posts_routes", __name__)


@bp.get("/api/posts")
def api_posts():
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    if ensure_post_store_schema is None or db_list_posts is None:
        return jsonify({"error": "Post store module unavailable"}), 500

    try:
        ensure_post_store_schema()
        limit = int((request.args.get("limit") or "20").strip() or "20")
        rows = db_list_posts(limit=limit)
        return jsonify({"posts": rows})
    except Exception as e:
        return jsonify({"error": f"No se pudo cargar publicaciones: {e}"}), 500


@bp.post("/api/posts/<int:post_id>/retry-publish")
def api_posts_retry_publish(post_id: int):
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    missing = [
        name
        for name, ref in {
            "db_get_post": db_get_post,
            "db_mark_post_publish_attempt": db_mark_post_publish_attempt,
            "db_mark_post_publish_error": db_mark_post_publish_error,
            "db_mark_post_published": db_mark_post_published,
        }.items()
        if ref is None
    ]
    if missing:
        return jsonify({"error": f"Post store incompleto: {', '.join(missing)}"}), 500

    if is_running():
        return jsonify({"error": "Hay un pipeline en ejecución. Reintenta al terminar."}), 409

    try:
        post = db_get_post(post_id)
    except Exception as e:
        return jsonify({"error": f"No se pudo cargar el post {post_id}: {e}"}), 500

    if not post:
        return jsonify({"error": f"Post {post_id} no encontrado"}), 404

    status = str(post.get("status") or "").strip()
    if status not in RETRYABLE_STATUSES:
        return (
            jsonify(
                {
                    "error": (
                        f"El post {post_id} no es reintentable en estado '{status}'. "
                        f"Estados válidos: {sorted(RETRYABLE_STATUSES)}"
                    )
                }
            ),
            400,
        )

    # Safety net: before re-publishing, try to reconcile pending rows that were
    # actually published on Instagram but DB wasn't updated.
    if db_reconcile_pending_posts is not None:
        try:
            db_reconcile_pending_posts(limit=60, max_age_hours=72)
            refreshed = db_get_post(post_id)
            refreshed_status = str((refreshed or {}).get("status") or "").strip()
            refreshed_media_id = str((refreshed or {}).get("ig_media_id") or "").strip()
            if refreshed_status == "published_active" and refreshed_media_id:
                return jsonify(
                    {
                        "ok": True,
                        "post_id": post_id,
                        "media_id": refreshed_media_id,
                        "status": "published_active",
                        "reconciled": True,
                    }
                )
        except Exception:
            # If reconciliation fails, continue with explicit retry publish.
            pass

    topic = post.get("topic_payload") if isinstance(post.get("topic_payload"), dict) else {"topic": post.get("topic")}
    content = post.get("content_payload")
    strategy = post.get("strategy_payload")
    if not isinstance(content, dict) or not isinstance(strategy, dict):
        return (
            jsonify(
                {
                    "error": (
                        "No hay payload suficiente para reintentar este post. "
                        "Falta content_payload o strategy_payload."
                    )
                }
            ),
            400,
        )

    try:
        from modules.carousel_designer import create as create_slides
        from modules.publisher import publish as publish_carousel
        from modules.publisher import save_to_history as save_legacy_history

        image_paths = create_slides(content, topic=topic)
        db_mark_post_publish_attempt(post_id)
        media_id = publish_carousel(image_paths, content, strategy)
        db_mark_post_published(post_id=post_id, media_id=media_id)
        save_legacy_history(media_id, topic)
        return jsonify({"ok": True, "post_id": post_id, "media_id": media_id, "status": "published_active"})
    except Exception as e:
        tag, summary, code = classify_publish_error_text(str(e))
        try:
            db_mark_post_publish_error(
                post_id=post_id,
                error_tag=tag,
                error_code=code,
                error_message=f"{summary} | {str(e)[:1800]}",
            )
        except Exception:
            pass
        return jsonify({"error": summary, "tag": tag, "code": code, "detail": str(e)}), 500
    finally:
        try:
            for p in OUTPUT_DIR.glob("slide_*.png"):
                p.unlink(missing_ok=True)
        except Exception:
            pass


@bp.get("/api/db-status")
def api_db_status():
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    if get_post_store_db_runtime_info is None:
        return jsonify({"error": "Post store module unavailable"}), 500

    try:
        info = get_post_store_db_runtime_info()
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": f"No se pudo obtener estado DB: {e}"}), 500


@bp.post("/api/posts/sync-metrics")
def api_posts_sync_metrics():
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    if db_sync_post_metrics is None:
        return jsonify({"error": "Metrics sync module unavailable"}), 500

    data = request.get_json(silent=True) or {}
    raw_limit = data.get("limit", 20)
    try:
        limit = max(1, min(int(raw_limit), 200))
    except Exception:
        limit = 20

    try:
        result = db_sync_post_metrics(limit=limit)
        result["auto_interval_minutes"] = get_auto_sync_interval_minutes()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"No se pudieron sincronizar métricas: {e}"}), 500


@bp.post("/api/posts/sync-instagram")
def api_posts_sync_instagram():
    """
    Alias explícito para scheduler/manual sync (métricas + estado IG activo/borrado).
    """
    return api_posts_sync_metrics()
