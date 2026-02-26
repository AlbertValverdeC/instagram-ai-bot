"""
Sync Instagram metrics into the local post store.

This module reads recently published posts from DB, fetches metrics
from Instagram Graph API, and persists snapshots for later analysis.
"""

from __future__ import annotations

import logging
import random
import time

import requests

from config.settings import GRAPH_API_VERSION, META_ACCESS_TOKEN
from modules.post_store import list_posts_for_metrics_sync, save_metrics_snapshot

logger = logging.getLogger(__name__)


def _normalize_graph_version(raw: str) -> str:
    v = (raw or "v25.0").strip()
    if not v.startswith("v"):
        v = f"v{v}"
    return v


GRAPH_API_BASE = f"https://graph.facebook.com/{_normalize_graph_version(GRAPH_API_VERSION)}"


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
    return code in {1, 2, 4, 17, 32, 613}


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

        err_text = _meta_error_text(resp)
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

        raise RuntimeError(f"Meta GET {path} failed: {err_text}")

    raise RuntimeError(f"Meta GET {path} failed after retries")


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

    posts = list_posts_for_metrics_sync(limit=limit)
    if not posts:
        return {"checked": 0, "updated": 0, "failed": 0, "errors": []}

    checked = 0
    updated = 0
    failed = 0
    errors: list[dict] = []

    for row in posts:
        checked += 1
        try:
            metrics, raw = fetch_media_metrics(row.get("ig_media_id"))
            save_metrics_snapshot(
                post_id=int(row["id"]),
                metrics=metrics,
                raw_payload=raw,
            )
            updated += 1
            time.sleep(0.2)
        except Exception as e:
            failed += 1
            if len(errors) < 20:
                errors.append(
                    {
                        "post_id": row.get("id"),
                        "ig_media_id": row.get("ig_media_id"),
                        "error": str(e),
                    }
                )

    return {
        "checked": checked,
        "updated": updated,
        "failed": failed,
        "errors": errors,
    }
