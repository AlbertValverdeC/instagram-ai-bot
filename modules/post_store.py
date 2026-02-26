"""
Persistent store for published posts, source URLs, and engagement snapshots.

Goals:
  - Keep a durable publication history (instead of only history.json)
  - Prevent duplicate publications from the same source/topic
  - Enable dashboard listing and future analytics
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    select,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError

from config.settings import DATABASE_URL, DUPLICATE_TOPIC_WINDOW_DAYS, IS_CLOUD_RUN

logger = logging.getLogger(__name__)

_metadata = MetaData()
_engine = None

posts_table = Table(
    "posts",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ig_media_id", String(64), unique=True, nullable=True, index=True),
    Column("topic", Text, nullable=False),
    Column("topic_en", Text, nullable=True),
    Column("topic_hash", String(64), nullable=False, index=True),
    Column("caption", Text, nullable=True),
    Column("virality_score", Float, nullable=True),
    Column("status", String(32), nullable=False, server_default="published", index=True),
    Column("source_count", Integer, nullable=False, server_default="0"),
    Column("published_at", DateTime(timezone=True), nullable=True, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("topic_payload", JSON, nullable=True),
    Column("content_payload", JSON, nullable=True),
    Column("strategy_payload", JSON, nullable=True),
)

post_sources_table = Table(
    "post_sources",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("post_id", Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("source_url", Text, nullable=False),
    Column("source_hash", String(64), nullable=False, index=True),
    Column("domain", String(255), nullable=True, index=True),
    Column("article_published_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("source_hash", name="uq_post_sources_source_hash"),
)

post_metrics_table = Table(
    "post_metrics_snapshots",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("post_id", Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("collected_at", DateTime(timezone=True), nullable=False, server_default=func.now(), index=True),
    Column("impressions", Integer, nullable=True),
    Column("reach", Integer, nullable=True),
    Column("likes", Integer, nullable=True),
    Column("comments", Integer, nullable=True),
    Column("saves", Integer, nullable=True),
    Column("shares", Integer, nullable=True),
    Column("engagement_rate", Float, nullable=True),
    Column("raw_payload", JSON, nullable=True),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_maybe_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_domain(url: str) -> str:
    try:
        return urlsplit(url).netloc.lower()
    except Exception:
        return ""


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_topic(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def topic_hash(topic: str) -> str:
    norm = _normalize_topic(topic)
    if not norm:
        return ""
    return _hash_text(norm)


def canonical_source_url(url: str) -> str:
    """
    Canonicalize article URL for duplicate detection.

    Strategy:
      - normalize scheme/host casing
      - keep only path (drop query/fragment to avoid tracking params)
      - remove trailing slash except root
    """
    raw = str(url or "").strip()
    if not raw:
        return ""

    if "://" not in raw:
        raw = f"https://{raw}"

    try:
        parsed = urlsplit(raw)
    except Exception:
        return ""

    scheme = (parsed.scheme or "https").lower()
    host = (parsed.netloc or "").lower()
    path = parsed.path or "/"
    if path != "/":
        path = re.sub(r"/+$", "", path) or "/"
    if not host:
        return ""
    return urlunsplit((scheme, host, path, "", ""))


def source_hash(url: str) -> str:
    canon = canonical_source_url(url)
    if not canon:
        return ""
    return _hash_text(canon)


def get_engine():
    global _engine
    if _engine is not None:
        return _engine

    db_url = (DATABASE_URL or "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL is empty")

    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    _engine = create_engine(
        db_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    return _engine


def get_db_runtime_info() -> dict:
    """
    Return safe DB runtime information for logs/UI.
    """
    db_url = (DATABASE_URL or "").strip()
    if not db_url:
        return {
            "configured": False,
            "database_url_masked": "",
            "dialect": "unknown",
            "is_sqlite": False,
            "is_cloud_run": IS_CLOUD_RUN,
            "persistent_recommended": IS_CLOUD_RUN,
            "persistent_ok": False,
            "warning": "DATABASE_URL vacío",
        }

    dialect = "unknown"
    masked_url = db_url
    is_sqlite = db_url.lower().startswith("sqlite")
    try:
        parsed = make_url(db_url)
        dialect = parsed.get_backend_name() or "unknown"
        masked_url = parsed.render_as_string(hide_password=True)
        is_sqlite = dialect == "sqlite"
    except Exception:
        # Keep safe fallback above.
        pass

    persistent_ok = not is_sqlite
    warning = None
    if IS_CLOUD_RUN and is_sqlite:
        warning = (
            "SQLite en Cloud Run no es persistente entre reinicios/despliegues. "
            "Configura DATABASE_URL con PostgreSQL."
        )

    return {
        "configured": True,
        "database_url_masked": masked_url,
        "dialect": dialect,
        "is_sqlite": is_sqlite,
        "is_cloud_run": IS_CLOUD_RUN,
        "persistent_recommended": IS_CLOUD_RUN,
        "persistent_ok": persistent_ok,
        "warning": warning,
    }


def ensure_schema():
    try:
        _metadata.create_all(get_engine())
    except OperationalError as e:
        # In concurrent startup races on SQLite, CREATE TABLE can collide.
        if "already exists" in str(e).lower():
            logger.debug("Post store schema already exists; continuing")
            return
        raise


def find_duplicate_candidate(
    topic: str,
    source_urls: list[str] | None,
    *,
    topic_window_days: int | None = None,
) -> dict | None:
    """
    Check if candidate topic/sources were already published recently.

    Returns:
      None if no duplicate, else a dict describing the duplicate reason.
    """
    ensure_schema()
    window_days = topic_window_days or DUPLICATE_TOPIC_WINDOW_DAYS
    src_urls = source_urls or []

    with get_engine().begin() as conn:
        # Hard duplicate by source URL hash.
        for original in src_urls:
            canon = canonical_source_url(original)
            shash = source_hash(original)
            if not canon or not shash:
                continue

            row = conn.execute(
                select(
                    posts_table.c.id,
                    posts_table.c.topic,
                    posts_table.c.ig_media_id,
                    posts_table.c.published_at,
                    post_sources_table.c.source_url,
                )
                .join(post_sources_table, post_sources_table.c.post_id == posts_table.c.id)
                .where(post_sources_table.c.source_hash == shash)
                .where(posts_table.c.status == "published")
                .order_by(posts_table.c.published_at.desc(), posts_table.c.id.desc())
                .limit(1)
            ).mappings().first()
            if row:
                return {
                    "kind": "source_url",
                    "source_url": canon,
                    "existing_post_id": row["id"],
                    "existing_topic": row["topic"],
                    "existing_media_id": row["ig_media_id"],
                    "existing_published_at": (
                        row["published_at"].isoformat() if row["published_at"] else None
                    ),
                }

        # Soft duplicate by topic hash in recent window.
        thash = topic_hash(topic)
        if thash:
            cutoff = _utc_now() - timedelta(days=window_days)
            row = conn.execute(
                select(
                    posts_table.c.id,
                    posts_table.c.topic,
                    posts_table.c.ig_media_id,
                    posts_table.c.published_at,
                )
                .where(posts_table.c.topic_hash == thash)
                .where(posts_table.c.status == "published")
                .where(posts_table.c.published_at >= cutoff)
                .order_by(posts_table.c.published_at.desc(), posts_table.c.id.desc())
                .limit(1)
            ).mappings().first()
            if row:
                return {
                    "kind": "topic_hash",
                    "topic": topic,
                    "existing_post_id": row["id"],
                    "existing_topic": row["topic"],
                    "existing_media_id": row["ig_media_id"],
                    "existing_published_at": (
                        row["published_at"].isoformat() if row["published_at"] else None
                    ),
                    "window_days": window_days,
                }
    return None


def save_published_post(
    media_id: str,
    topic: dict,
    content: dict,
    strategy: dict,
    *,
    status: str = "published",
) -> int:
    """
    Persist a published post and related source URLs.
    """
    ensure_schema()
    published_at = _utc_now()
    topic_text = str(topic.get("topic", "")).strip()
    source_urls = topic.get("source_urls") or []
    if not isinstance(source_urls, list):
        source_urls = []

    with get_engine().begin() as conn:
        insert_result = conn.execute(
            posts_table.insert().values(
                ig_media_id=media_id,
                topic=topic_text or "(sin topic)",
                topic_en=str(topic.get("topic_en", "")).strip() or None,
                topic_hash=topic_hash(topic_text) or _hash_text(f"post-{media_id}-{published_at.isoformat()}"),
                caption=str(strategy.get("full_caption") or content.get("caption") or "").strip() or None,
                virality_score=topic.get("virality_score"),
                status=status,
                source_count=0,
                published_at=published_at,
                topic_payload=topic,
                content_payload=content,
                strategy_payload=strategy,
            )
        )
        post_id = insert_result.inserted_primary_key[0]

        source_count = 0
        for raw_url in source_urls:
            canon = canonical_source_url(raw_url)
            shash = source_hash(raw_url)
            if not canon or not shash:
                continue
            try:
                conn.execute(
                    post_sources_table.insert().values(
                        post_id=post_id,
                        source_url=canon,
                        source_hash=shash,
                        domain=_extract_domain(canon),
                        article_published_at=None,
                    )
                )
                source_count += 1
            except IntegrityError:
                # Source already exists from a previous post -> useful for duplicate diagnostics.
                logger.warning("Source URL already exists in DB (duplicate hash): %s", canon)

        conn.execute(
            posts_table.update()
            .where(posts_table.c.id == post_id)
            .values(source_count=source_count)
        )

    return int(post_id)


def list_posts_for_metrics_sync(limit: int = 50) -> list[dict]:
    """
    Return published posts with IG media id, newest first.
    Useful as source set for metrics synchronization jobs.
    """
    ensure_schema()
    safe_limit = max(1, min(int(limit or 50), 500))
    with get_engine().begin() as conn:
        rows = conn.execute(
            select(
                posts_table.c.id,
                posts_table.c.ig_media_id,
                posts_table.c.topic,
                posts_table.c.published_at,
            )
            .where(posts_table.c.status == "published")
            .where(posts_table.c.ig_media_id.is_not(None))
            .where(posts_table.c.ig_media_id != "")
            .order_by(posts_table.c.published_at.desc(), posts_table.c.id.desc())
            .limit(safe_limit)
        ).mappings().all()
    return [dict(r) for r in rows]


def save_metrics_snapshot(
    *,
    post_id: int,
    metrics: dict,
    raw_payload: dict | None = None,
    collected_at: datetime | None = None,
) -> int:
    """
    Persist a metrics snapshot for one post.
    """
    ensure_schema()
    if not post_id:
        raise ValueError("post_id is required")

    likes = _to_int(metrics.get("likes"))
    comments = _to_int(metrics.get("comments"))
    saves = _to_int(metrics.get("saves"))
    shares = _to_int(metrics.get("shares"))
    impressions = _to_int(metrics.get("impressions"))
    reach = _to_int(metrics.get("reach"))
    engagement_rate = _to_float(metrics.get("engagement_rate"))

    if engagement_rate is None and reach and reach > 0:
        interactions = sum(v or 0 for v in (likes, comments, saves, shares))
        engagement_rate = round((interactions / reach) * 100.0, 4)

    with get_engine().begin() as conn:
        result = conn.execute(
            post_metrics_table.insert().values(
                post_id=post_id,
                collected_at=collected_at or _utc_now(),
                impressions=impressions,
                reach=reach,
                likes=likes,
                comments=comments,
                saves=saves,
                shares=shares,
                engagement_rate=engagement_rate,
                raw_payload=raw_payload,
            )
        )
    return int(result.inserted_primary_key[0])


def save_metrics_snapshot_by_media_id(
    *,
    ig_media_id: str,
    metrics: dict,
    raw_payload: dict | None = None,
    collected_at: datetime | None = None,
) -> int | None:
    """
    Persist metrics snapshot looking up the post by IG media id.
    Returns snapshot id, or None if media id not found in DB.
    """
    ensure_schema()
    media_id = str(ig_media_id or "").strip()
    if not media_id:
        return None

    with get_engine().begin() as conn:
        row = conn.execute(
            select(posts_table.c.id).where(posts_table.c.ig_media_id == media_id).limit(1)
        ).mappings().first()
    if not row:
        return None

    return save_metrics_snapshot(
        post_id=int(row["id"]),
        metrics=metrics,
        raw_payload=raw_payload,
        collected_at=collected_at,
    )


def list_posts(limit: int = 50) -> list[dict]:
    ensure_schema()
    safe_limit = max(1, min(int(limit or 50), 200))
    with get_engine().begin() as conn:
        post_rows = conn.execute(
            select(
                posts_table.c.id,
                posts_table.c.ig_media_id,
                posts_table.c.topic,
                posts_table.c.virality_score,
                posts_table.c.status,
                posts_table.c.source_count,
                posts_table.c.published_at,
            )
            .order_by(posts_table.c.published_at.desc(), posts_table.c.id.desc())
            .limit(safe_limit)
        ).mappings().all()
        if not post_rows:
            return []

        post_ids = [row["id"] for row in post_rows]
        src_rows = conn.execute(
            select(post_sources_table.c.post_id, post_sources_table.c.source_url)
            .where(post_sources_table.c.post_id.in_(post_ids))
            .order_by(post_sources_table.c.id.asc())
        ).mappings().all()
        metric_rows = conn.execute(
            select(
                post_metrics_table.c.post_id,
                post_metrics_table.c.collected_at,
                post_metrics_table.c.impressions,
                post_metrics_table.c.reach,
                post_metrics_table.c.likes,
                post_metrics_table.c.comments,
                post_metrics_table.c.saves,
                post_metrics_table.c.shares,
                post_metrics_table.c.engagement_rate,
            )
            .where(post_metrics_table.c.post_id.in_(post_ids))
            .order_by(post_metrics_table.c.collected_at.desc(), post_metrics_table.c.id.desc())
        ).mappings().all()

    sources_by_post = {}
    for row in src_rows:
        sources_by_post.setdefault(row["post_id"], []).append(row["source_url"])

    latest_metrics_by_post = {}
    for row in metric_rows:
        post_id = row["post_id"]
        if post_id in latest_metrics_by_post:
            continue
        latest_metrics_by_post[post_id] = {
            "metrics_collected_at": (
                row["collected_at"].isoformat() if row["collected_at"] else None
            ),
            "impressions": row["impressions"],
            "reach": row["reach"],
            "likes": row["likes"],
            "comments": row["comments"],
            "saves": row["saves"],
            "shares": row["shares"],
            "engagement_rate": row["engagement_rate"],
        }

    out = []
    for row in post_rows:
        published_at = row["published_at"]
        metrics = latest_metrics_by_post.get(row["id"], {})
        out.append(
            {
                "id": row["id"],
                "ig_media_id": row["ig_media_id"],
                "topic": row["topic"],
                "status": row["status"],
                "virality_score": row["virality_score"],
                "source_count": row["source_count"],
                "published_at": published_at.isoformat() if published_at else None,
                "source_urls": sources_by_post.get(row["id"], []),
                "metrics_collected_at": metrics.get("metrics_collected_at"),
                "impressions": metrics.get("impressions"),
                "reach": metrics.get("reach"),
                "likes": metrics.get("likes"),
                "comments": metrics.get("comments"),
                "saves": metrics.get("saves"),
                "shares": metrics.get("shares"),
                "engagement_rate": metrics.get("engagement_rate"),
            }
        )
    return out
