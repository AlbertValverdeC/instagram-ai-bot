"""
Sync Instagram metrics into the local post store.

This module reads recently published posts from DB, fetches metrics
from Instagram Graph API, and persists snapshots for later analysis.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timedelta, timezone

import requests

from config.settings import GRAPH_API_VERSION, INSTAGRAM_ACCOUNT_ID, META_ACCESS_TOKEN
from modules.post_store import (
    list_pending_posts_for_ig_reconcile,
    list_posts_for_metrics_sync,
    mark_post_ig_active,
    mark_post_ig_deleted,
    mark_post_published,
    save_metrics_snapshot,
)

logger = logging.getLogger(__name__)


def _normalize_graph_version(raw: str) -> str:
    v = (raw or "v25.0").strip()
    if not v.startswith("v"):
        v = f"v{v}"
    return v


GRAPH_API_BASE = f"https://graph.facebook.com/{_normalize_graph_version(GRAPH_API_VERSION)}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_graph_datetime(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None


def _normalize_caption_for_match(text: str | None) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _meta_error_text(resp: requests.Response) -> str:
    try:
        payload = resp.json()
    except ValueError:
        body = (resp.text or "").strip()
        return f"HTTP {resp.status_code}: {body[:300]}"

    err = payload.get("error") if isinstance(payload, dict) else None
    if not err:
        return f"HTTP {resp.status_code}: {payload}"

    message = err.get("message", "Unknown Meta error")
    code = err.get("code")
    subcode = err.get("error_subcode")
    fbtrace = err.get("fbtrace_id")
    parts = [f"HTTP {resp.status_code}", message]
    if code is not None:
        parts.append(f"code={code}")
    if subcode is not None:
        parts.append(f"subcode={subcode}")
    if fbtrace:
        parts.append(f"fbtrace_id={fbtrace}")
    return " | ".join(parts)


def _is_meta_transient_error(resp: requests.Response) -> bool:
    if resp.status_code >= 500:
        return True
    try:
        payload = resp.json()
    except ValueError:
        return False
    err = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(err, dict):
        return False
    if bool(err.get("is_transient")):
        return True
    code = err.get("code")
    subcode = err.get("error_subcode")
    return code in {1, 2, 4, 17, 32, 613} or subcode in {2207051, 2207085}


def _meta_error_details_from_response(resp: requests.Response) -> dict:
    details = {
        "status_code": resp.status_code,
        "code": None,
        "subcode": None,
        "message": "",
        "text": "",
    }
    details["text"] = _meta_error_text(resp)
    try:
        payload = resp.json()
    except ValueError:
        details["message"] = (resp.text or "").strip()[:300]
        return details
    err = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(err, dict):
        details["code"] = err.get("code")
        details["subcode"] = err.get("error_subcode")
        details["message"] = str(err.get("message") or "")[:300]
    return details


def _is_missing_or_deleted_media_error(error_text: str, *, code=None, subcode=None) -> bool:
    low = (error_text or "").lower()
    if code == 100 and subcode == 33:
        return True
    if "unsupported get request" in low and "subcode=33" in low:
        return True
    if "does not exist" in low and "object" in low:
        return True
    return False


def _retry_sleep(attempt: int, *, base: float = 0.8, cap: float = 8.0):
    delay = min(cap, base * (2 ** max(0, attempt - 1)))
    delay += random.uniform(0.0, 0.35)
    time.sleep(delay)


def _graph_get(path: str, params: dict, *, timeout: int = 30, retries: int = 3) -> dict:
    url = f"{GRAPH_API_BASE}/{path.lstrip('/')}"
    attempts = max(1, retries + 1)

    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            if attempt >= attempts:
                raise RuntimeError(f"Meta GET {path} network failure: {exc}") from exc
            logger.warning(
                "Meta GET %s network error (attempt %d/%d): %s. Reintentando...",
                path,
                attempt,
                attempts,
                exc,
            )
            _retry_sleep(attempt)
            continue

        if resp.ok:
            return resp.json()

        details = _meta_error_details_from_response(resp)
        err_text = details["text"]
        if attempt < attempts and _is_meta_transient_error(resp):
            logger.warning(
                "Meta GET %s error transitorio (attempt %d/%d): %s. Reintentando...",
                path,
                attempt,
                attempts,
                err_text,
            )
            _retry_sleep(attempt)
            continue

        raise RuntimeError(
            f"Meta GET {path} failed: {err_text}"
            f" | details(code={details['code']},subcode={details['subcode']})"
        )

    raise RuntimeError(f"Meta GET {path} failed after retries")


def _get_recent_account_media(limit: int = 50) -> list[dict]:
    if not INSTAGRAM_ACCOUNT_ID:
        raise RuntimeError("INSTAGRAM_ACCOUNT_ID no configurado")
    safe_limit = max(1, min(int(limit or 50), 100))
    payload = _graph_get(
        f"{INSTAGRAM_ACCOUNT_ID}/media",
        {
            "fields": "id,caption,permalink,timestamp,media_type,media_product_type",
            "limit": str(safe_limit),
            "access_token": META_ACCESS_TOKEN,
        },
    )
    rows = payload.get("data") if isinstance(payload, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _is_media_candidate_for_post(*, post: dict, media: dict, max_age_hours: int) -> bool:
    expected_caption = _normalize_caption_for_match(post.get("caption"))
    media_caption = _normalize_caption_for_match(media.get("caption"))
    if not expected_caption or not media_caption:
        return False
    if expected_caption != media_caption:
        return False

    post_created = post.get("created_at")
    if isinstance(post_created, datetime):
        created_at = post_created if post_created.tzinfo else post_created.replace(tzinfo=timezone.utc)
    else:
        created_at = None
    media_ts = _parse_graph_datetime(media.get("timestamp"))
    now = _utc_now()

    if media_ts is not None:
        if media_ts < (now - timedelta(hours=max(1, int(max_age_hours)))):
            return False
        # Small skew tolerance for clock drift between DB and Graph.
        if created_at is not None and media_ts < (created_at - timedelta(minutes=20)):
            return False

    media_product_type = str(media.get("media_product_type") or "").upper()
    if media_product_type and media_product_type not in {"FEED"}:
        return False

    return True


def reconcile_pending_posts_with_instagram(*, limit: int = 40, max_age_hours: int = 72) -> dict:
    """
    Detect already-published IG posts for local rows still marked as generated/error.
    """
    if not META_ACCESS_TOKEN:
        raise RuntimeError("META_ACCESS_TOKEN no configurado")
    if not INSTAGRAM_ACCOUNT_ID:
        raise RuntimeError("INSTAGRAM_ACCOUNT_ID no configurado")

    pending_posts = list_pending_posts_for_ig_reconcile(limit=limit, max_age_hours=max_age_hours)
    if not pending_posts:
        return {"pending_checked": 0, "pending_reconciled": 0, "pending_errors": []}

    media_rows = _get_recent_account_media(limit=max(40, min(100, len(pending_posts) * 3)))
    reconciled = 0
    errors: list[dict] = []
    used_media_ids: set[str] = set()

    for post in pending_posts:
        post_id = int(post["id"])
        match = None
        for media in media_rows:
            if _is_media_candidate_for_post(post=post, media=media, max_age_hours=max_age_hours):
                match = media
                break
        if not match:
            continue

        media_id = str(match.get("id") or "").strip()
        if not media_id:
            continue
        if media_id in used_media_ids:
            continue

        try:
            mark_post_published(post_id=post_id, media_id=media_id)
            used_media_ids.add(media_id)
            reconciled += 1
            logger.info(
                "Reconciled pending post id=%s with IG media_id=%s permalink=%s",
                post_id,
                media_id,
                match.get("permalink") or "-",
            )
        except Exception as e:
            if len(errors) < 20:
                errors.append({"post_id": post_id, "error": str(e)})

    return {
        "pending_checked": len(pending_posts),
        "pending_reconciled": reconciled,
        "pending_errors": errors,
    }


def _extract_insights(payload: dict) -> dict:
    """
    Normalize Graph insights payload into flat numeric metrics.
    """
    out: dict = {}
    items = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        values = item.get("values")
        if not name or not isinstance(values, list) or not values:
            continue
        value = values[0].get("value") if isinstance(values[0], dict) else None
        if isinstance(value, (int, float)):
            out[name] = value
    return out


def fetch_media_metrics(ig_media_id: str) -> tuple[dict, dict]:
    """
    Return (normalized_metrics, raw_payloads) for one IG media id.
    """
    if not META_ACCESS_TOKEN:
        raise RuntimeError("META_ACCESS_TOKEN no configurado")

    media_id = str(ig_media_id or "").strip()
    if not media_id:
        raise ValueError("ig_media_id vacío")

    base_payload = _graph_get(
        media_id,
        {
            "fields": "id,like_count,comments_count,media_type,media_product_type,permalink,timestamp",
            "access_token": META_ACCESS_TOKEN,
        },
    )

    metrics = {
        "likes": base_payload.get("like_count"),
        "comments": base_payload.get("comments_count"),
    }
    raw_payloads: dict = {"media": base_payload}

    insight_metrics_candidates = [
        "impressions,reach,saved,shares",
        "impressions,reach,saved",
        "impressions,reach",
    ]
    insight_payload = None
    for metric_set in insight_metrics_candidates:
        try:
            insight_payload = _graph_get(
                f"{media_id}/insights",
                {"metric": metric_set, "access_token": META_ACCESS_TOKEN},
                retries=1,
            )
            break
        except Exception as e:
            # Some media/account combinations do not expose all metrics.
            last_error = str(e).lower()
            if "metric" in last_error or "insights" in last_error or "code=100" in last_error:
                continue
            raise

    if insight_payload:
        raw_payloads["insights"] = insight_payload
        insight_map = _extract_insights(insight_payload)
        for k in ("impressions", "reach", "saved", "shares"):
            if k in insight_map:
                metrics["saves" if k == "saved" else k] = insight_map[k]

    return metrics, raw_payloads


def sync_recent_post_metrics(limit: int = 30) -> dict:
    """
    Fetch and persist metrics snapshots for latest published posts.
    """
    if not META_ACCESS_TOKEN:
        raise RuntimeError("META_ACCESS_TOKEN no configurado")

    reconcile_result = reconcile_pending_posts_with_instagram(
        limit=max(30, min(int(limit or 30), 120)),
        max_age_hours=72,
    )

    posts = list_posts_for_metrics_sync(limit=limit)
    if not posts:
        return {
            "checked": 0,
            "updated": 0,
            "failed": 0,
            "errors": [],
            "pending_checked": reconcile_result.get("pending_checked", 0),
            "pending_reconciled": reconcile_result.get("pending_reconciled", 0),
            "pending_errors": reconcile_result.get("pending_errors", []),
        }

    checked = 0
    updated = 0
    failed = 0
    errors: list[dict] = []

    for row in posts:
        checked += 1
        post_id = int(row["id"])
        media_id = row.get("ig_media_id")
        try:
            metrics, raw = fetch_media_metrics(media_id)
            save_metrics_snapshot(
                post_id=post_id,
                metrics=metrics,
                raw_payload=raw,
            )
            mark_post_ig_active(post_id=post_id)
            updated += 1
            time.sleep(0.2)
        except Exception as e:
            failed += 1
            err_text = str(e)
            if _is_missing_or_deleted_media_error(err_text):
                try:
                    mark_post_ig_deleted(post_id=post_id, reason=err_text)
                except Exception:
                    pass
            if len(errors) < 20:
                errors.append(
                    {
                        "post_id": post_id,
                        "ig_media_id": media_id,
                        "error": err_text,
                        "deleted_or_unavailable": _is_missing_or_deleted_media_error(err_text),
                    }
                )

    return {
        "checked": checked,
        "updated": updated,
        "failed": failed,
        "errors": errors,
        "pending_checked": reconcile_result.get("pending_checked", 0),
        "pending_reconciled": reconcile_result.get("pending_reconciled", 0),
        "pending_errors": reconcile_result.get("pending_errors", []),
    }
