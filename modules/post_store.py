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
import threading
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
    delete,
    func,
    inspect,
    select,
    text,
    update,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, OperationalError

from config.settings import DATABASE_URL, DUPLICATE_TOPIC_WINDOW_DAYS, IS_CLOUD_RUN, OUTPUT_DIR

logger = logging.getLogger(__name__)

_metadata = MetaData()
_engine = None
_schema_initialized = False
_schema_lock = threading.Lock()

POST_STATUS_GENERATED = "generated"
POST_STATUS_DRAFT = "draft"
POST_STATUS_PUBLISH_ERROR = "publish_error"
POST_STATUS_PUBLISHED = "published"  # Legacy compatibility
POST_STATUS_PUBLISHED_ACTIVE = "published_active"
POST_STATUS_PUBLISHED_DELETED = "published_deleted"

PUBLISHED_STATUSES = {
    POST_STATUS_PUBLISHED,
    POST_STATUS_PUBLISHED_ACTIVE,
}
RETRYABLE_STATUSES = {
    POST_STATUS_GENERATED,
    POST_STATUS_PUBLISH_ERROR,
}
PUBLISHABLE_STATUSES = {
    POST_STATUS_DRAFT,
    POST_STATUS_GENERATED,
    POST_STATUS_PUBLISH_ERROR,
}

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
    Column("ig_status", String(32), nullable=False, server_default="unknown", index=True),
    Column("source_count", Integer, nullable=False, server_default="0"),
    Column("publish_attempts", Integer, nullable=False, server_default="0"),
    Column("last_publish_attempt_at", DateTime(timezone=True), nullable=True),
    Column("last_error_tag", String(64), nullable=True, index=True),
    Column("last_error_code", String(64), nullable=True),
    Column("last_error_message", Text, nullable=True),
    Column("ig_last_checked_at", DateTime(timezone=True), nullable=True),
    Column("published_at", DateTime(timezone=True), nullable=True, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("topic_payload", JSON, nullable=True),
    Column("proposal_payload", JSON, nullable=True),
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

scheduler_config_table = Table(
    "scheduler_config",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("enabled", Integer, nullable=False, server_default="0"),
    Column("schedule", JSON, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

content_queue_table = Table(
    "content_queue",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scheduled_date", String(10), nullable=False, index=True),
    Column("scheduled_time", String(5), nullable=True),
    Column("topic", Text, nullable=True),
    Column("template", Integer, nullable=True),
    Column("status", String(20), nullable=False, server_default="pending", index=True),
    Column("runs_total", Integer, nullable=False, server_default="1"),
    Column("runs_completed", Integer, nullable=False, server_default="0"),
    Column("post_id", Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True),
    Column("result_message", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint("scheduled_date", name="uq_content_queue_date"),
)

DEFAULT_SCHEDULE = {
    "monday": {"enabled": True, "time": "08:30", "posts_per_day": 1, "times": ["08:30"]},
    "tuesday": {"enabled": True, "time": "08:30", "posts_per_day": 1, "times": ["08:30"]},
    "wednesday": {"enabled": True, "time": "08:30", "posts_per_day": 1, "times": ["08:30"]},
    "thursday": {"enabled": True, "time": "08:30", "posts_per_day": 1, "times": ["08:30"]},
    "friday": {"enabled": True, "time": "08:30", "posts_per_day": 1, "times": ["08:30"]},
    "saturday": {"enabled": True, "time": "10:00", "posts_per_day": 1, "times": ["10:00"]},
    "sunday": {"enabled": False, "time": None, "posts_per_day": 1, "times": []},
}

DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
SCHEDULER_MIN_POSTS_PER_DAY = 1
SCHEDULER_MAX_POSTS_PER_DAY = 10
SCHEDULER_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
HISTORY_SLIDES_ROOT = OUTPUT_DIR / "history"
HISTORY_SLIDES_KEY = "history_slides"
HISTORY_PREVIEW_SLIDES_KEY = "history_preview_slides"


def _utc_now() -> datetime:
    return datetime.now(UTC)


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


def _normalize_posts_per_day(value) -> int:
    parsed = _to_int(value)
    if parsed is None:
        return SCHEDULER_MIN_POSTS_PER_DAY
    return max(SCHEDULER_MIN_POSTS_PER_DAY, min(parsed, SCHEDULER_MAX_POSTS_PER_DAY))


def _next_time_slot(time_str: str, *, step_hours: int = 2) -> str:
    hour = int(time_str[:2])
    minute = int(time_str[3:])
    next_hour = (hour + step_hours) % 24
    return f"{next_hour:02d}:{minute:02d}"


def _normalize_day_times(day_cfg: dict, default_time: str | None, posts_per_day: int) -> list[str]:
    raw_times = day_cfg.get("times")
    normalized_times: list[str] = []

    if isinstance(raw_times, list):
        for raw_time in raw_times:
            candidate = str(raw_time or "").strip()
            if not SCHEDULER_TIME_RE.match(candidate):
                continue
            if candidate in normalized_times:
                continue
            normalized_times.append(candidate)

    fallback_time = str(day_cfg.get("time") or default_time or "").strip()
    if fallback_time and SCHEDULER_TIME_RE.match(fallback_time) and fallback_time not in normalized_times:
        normalized_times.insert(0, fallback_time)

    if not normalized_times and posts_per_day > 0:
        normalized_times.append("08:30")

    while len(normalized_times) < posts_per_day:
        candidate = _next_time_slot(normalized_times[-1], step_hours=2)
        for _ in range(24):
            if candidate not in normalized_times:
                break
            candidate = _next_time_slot(candidate, step_hours=1)
        if candidate in normalized_times:
            break
        normalized_times.append(candidate)

    return normalized_times[:posts_per_day]


def resolve_day_schedule_times(day_cfg: dict | None) -> list[str]:
    cfg = day_cfg if isinstance(day_cfg, dict) else {}
    posts_per_day = _normalize_posts_per_day(cfg.get("posts_per_day", SCHEDULER_MIN_POSTS_PER_DAY))
    return _normalize_day_times(cfg, str(cfg.get("time") or "").strip() or None, posts_per_day)


def _normalize_schedule(schedule: dict | None) -> dict:
    normalized = {}
    source = schedule if isinstance(schedule, dict) else {}
    for day_name in DAY_NAMES:
        default_cfg = DEFAULT_SCHEDULE[day_name]
        day_cfg = source.get(day_name)
        if not isinstance(day_cfg, dict):
            day_cfg = {}

        enabled = bool(day_cfg.get("enabled", default_cfg["enabled"]))
        posts_per_day = _normalize_posts_per_day(day_cfg.get("posts_per_day", default_cfg["posts_per_day"]))
        times = _normalize_day_times(day_cfg, default_cfg.get("time"), posts_per_day)
        time_value = times[0] if times else None

        normalized[day_name] = {
            "enabled": enabled,
            "time": time_value,
            "posts_per_day": posts_per_day,
            "times": times,
        }
    return normalized


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


def _sanitize_slide_ref(value: str) -> str | None:
    raw = str(value or "").strip().replace("\\", "/").lstrip("/")
    if not raw:
        return None
    parts = [part for part in raw.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def _extract_history_slide_refs(content_payload: dict | None) -> tuple[list[str], list[str]]:
    if not isinstance(content_payload, dict):
        return [], []

    all_refs: list[str] = []
    raw_refs = content_payload.get(HISTORY_SLIDES_KEY)
    if isinstance(raw_refs, list):
        for raw in raw_refs:
            ref = _sanitize_slide_ref(str(raw or ""))
            if ref and ref not in all_refs:
                all_refs.append(ref)

    preview_refs: list[str] = []
    raw_preview = content_payload.get(HISTORY_PREVIEW_SLIDES_KEY)
    if isinstance(raw_preview, list):
        for raw in raw_preview:
            ref = _sanitize_slide_ref(str(raw or ""))
            if ref and ref in all_refs and ref not in preview_refs:
                preview_refs.append(ref)

    if not preview_refs and all_refs:
        preview_refs = all_refs[:3]

    return all_refs, preview_refs


def save_post_history_slides(
    post_id: int,
    slide_refs: list[str],
    *,
    preview_limit: int = 3,
) -> list[str]:
    ensure_schema()
    safe_post_id = int(post_id)
    safe_preview_limit = max(1, min(int(preview_limit or 3), 8))

    normalized_refs: list[str] = []
    for raw in slide_refs:
        ref = _sanitize_slide_ref(str(raw or ""))
        if not ref or ref in normalized_refs:
            continue
        normalized_refs.append(ref)

    if not normalized_refs:
        return []

    with get_engine().begin() as conn:
        row = (
            conn.execute(
                select(posts_table.c.content_payload).where(posts_table.c.id == safe_post_id).limit(1)
            )
            .mappings()
            .first()
        )
        if not row:
            return []

        payload = row.get("content_payload")
        if not isinstance(payload, dict):
            payload = {}
        else:
            payload = dict(payload)

        payload[HISTORY_SLIDES_KEY] = normalized_refs
        payload[HISTORY_PREVIEW_SLIDES_KEY] = normalized_refs[:safe_preview_limit]

        conn.execute(
            posts_table.update().where(posts_table.c.id == safe_post_id).values(content_payload=payload)
        )

    return normalized_refs


def archive_post_slides(
    *,
    post_id: int,
    slide_paths: list[Path | str],
    preview_limit: int = 3,
) -> list[str]:
    safe_post_id = int(post_id)
    target_dir = HISTORY_SLIDES_ROOT / str(safe_post_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_refs: list[str] = []
    for idx, raw_path in enumerate(slide_paths):
        path_obj = Path(raw_path)
        if not path_obj.exists() or not path_obj.is_file():
            continue
        suffix = path_obj.suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg"}:
            continue
        normalized_suffix = ".jpg" if suffix == ".jpeg" else suffix
        filename = f"slide_{idx:02d}{normalized_suffix}"
        dest = target_dir / filename
        try:
            shutil.copy2(path_obj, dest)
        except Exception as exc:
            logger.warning("Could not archive slide for post %s (%s): %s", safe_post_id, path_obj, exc)
            continue
        ref = f"history/{safe_post_id}/{filename}"
        stored_refs.append(ref)

    if not stored_refs:
        return []

    return save_post_history_slides(
        safe_post_id,
        stored_refs,
        preview_limit=preview_limit,
    )


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
            "SQLite en Cloud Run no es persistente entre reinicios/despliegues. Configura DATABASE_URL con PostgreSQL."
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


_POSTS_MIGRATIONS = [
    ("ig_status", "ALTER TABLE posts ADD COLUMN ig_status VARCHAR(32)"),
    ("publish_attempts", "ALTER TABLE posts ADD COLUMN publish_attempts INTEGER DEFAULT 0"),
    ("last_publish_attempt_at", "ALTER TABLE posts ADD COLUMN last_publish_attempt_at TIMESTAMP"),
    ("last_error_tag", "ALTER TABLE posts ADD COLUMN last_error_tag VARCHAR(64)"),
    ("last_error_code", "ALTER TABLE posts ADD COLUMN last_error_code VARCHAR(64)"),
    ("last_error_message", "ALTER TABLE posts ADD COLUMN last_error_message TEXT"),
    ("ig_last_checked_at", "ALTER TABLE posts ADD COLUMN ig_last_checked_at TIMESTAMP"),
    ("proposal_payload", "ALTER TABLE posts ADD COLUMN proposal_payload JSON"),
]

_CONTENT_QUEUE_MIGRATIONS = [
    ("runs_total", "ALTER TABLE content_queue ADD COLUMN runs_total INTEGER DEFAULT 1"),
    ("runs_completed", "ALTER TABLE content_queue ADD COLUMN runs_completed INTEGER DEFAULT 0"),
]


def _run_schema_migrations():
    """
    Lightweight in-place migrations for environments without Alembic.
    """
    engine = get_engine()
    with engine.begin() as conn:
        insp = inspect(conn)
        table_names = set(insp.get_table_names())
        if "posts" not in table_names:
            return

        existing = {c["name"] for c in insp.get_columns("posts")}
        for column_name, sql in _POSTS_MIGRATIONS:
            if column_name in existing:
                continue
            logger.info("Applying post_store migration: add posts.%s", column_name)
            conn.execute(text(sql))

        # Backfill sensible defaults for nullable historical rows.
        conn.execute(text("UPDATE posts SET publish_attempts = 0 WHERE publish_attempts IS NULL"))
        conn.execute(text("UPDATE posts SET ig_status = 'unknown' WHERE ig_status IS NULL OR ig_status = ''"))
        conn.execute(
            text("UPDATE posts SET status = :active WHERE status = :legacy"),
            {"active": POST_STATUS_PUBLISHED_ACTIVE, "legacy": POST_STATUS_PUBLISHED},
        )

        index_names = {idx.get("name") for idx in insp.get_indexes("posts")}
        if "ix_posts_ig_status" not in index_names:
            conn.execute(text("CREATE INDEX ix_posts_ig_status ON posts (ig_status)"))
        if "ix_posts_last_error_tag" not in index_names:
            conn.execute(text("CREATE INDEX ix_posts_last_error_tag ON posts (last_error_tag)"))

        if "content_queue" in table_names:
            queue_columns = {c["name"] for c in insp.get_columns("content_queue")}
            for column_name, sql in _CONTENT_QUEUE_MIGRATIONS:
                if column_name in queue_columns:
                    continue
                logger.info("Applying post_store migration: add content_queue.%s", column_name)
                conn.execute(text(sql))
            conn.execute(text("UPDATE content_queue SET runs_total = 1 WHERE runs_total IS NULL OR runs_total < 1"))
            conn.execute(
                text("UPDATE content_queue SET runs_completed = 0 WHERE runs_completed IS NULL OR runs_completed < 0")
            )
            conn.execute(
                text(
                    "UPDATE content_queue "
                    "SET runs_completed = runs_total "
                    "WHERE status = 'completed' AND runs_completed < runs_total"
                )
            )


def ensure_schema():
    global _schema_initialized
    if _schema_initialized:
        return

    with _schema_lock:
        if _schema_initialized:
            return
        try:
            _metadata.create_all(get_engine())
            _run_schema_migrations()
            _schema_initialized = True
        except OperationalError as e:
            # In concurrent startup races on SQLite, CREATE TABLE can collide.
            if "already exists" in str(e).lower():
                logger.debug("Post store schema already exists; continuing")
                _run_schema_migrations()
                _schema_initialized = True
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

            row = (
                conn.execute(
                    select(
                        posts_table.c.id,
                        posts_table.c.topic,
                        posts_table.c.ig_media_id,
                        posts_table.c.published_at,
                        post_sources_table.c.source_url,
                    )
                    .join(post_sources_table, post_sources_table.c.post_id == posts_table.c.id)
                    .where(post_sources_table.c.source_hash == shash)
                    .where(posts_table.c.status.in_(list(PUBLISHED_STATUSES)))
                    .order_by(posts_table.c.published_at.desc(), posts_table.c.id.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if row:
                return {
                    "kind": "source_url",
                    "source_url": canon,
                    "existing_post_id": row["id"],
                    "existing_topic": row["topic"],
                    "existing_media_id": row["ig_media_id"],
                    "existing_published_at": (row["published_at"].isoformat() if row["published_at"] else None),
                }

        # Soft duplicate by topic hash in recent window.
        thash = topic_hash(topic)
        if thash:
            cutoff = _utc_now() - timedelta(days=window_days)
            row = (
                conn.execute(
                    select(
                        posts_table.c.id,
                        posts_table.c.topic,
                        posts_table.c.ig_media_id,
                        posts_table.c.published_at,
                    )
                    .where(posts_table.c.topic_hash == thash)
                    .where(posts_table.c.status.in_(list(PUBLISHED_STATUSES)))
                    .where(posts_table.c.published_at >= cutoff)
                    .order_by(posts_table.c.published_at.desc(), posts_table.c.id.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if row:
                return {
                    "kind": "topic_hash",
                    "topic": topic,
                    "existing_post_id": row["id"],
                    "existing_topic": row["topic"],
                    "existing_media_id": row["ig_media_id"],
                    "existing_published_at": (row["published_at"].isoformat() if row["published_at"] else None),
                    "window_days": window_days,
                }
    return None


def _insert_post_sources(conn, *, post_id: int, source_urls: list[str]) -> int:
    source_count = 0
    for raw_url in source_urls:
        canon = canonical_source_url(raw_url)
        shash = source_hash(raw_url)
        if not canon or not shash:
            continue
        try:
            # Use SAVEPOINT so a duplicate IntegrityError doesn't abort the
            # outer PostgreSQL transaction (SQLite ignores this harmlessly).
            nested = conn.begin_nested()
            conn.execute(
                post_sources_table.insert().values(
                    post_id=post_id,
                    source_url=canon,
                    source_hash=shash,
                    domain=_extract_domain(canon),
                    article_published_at=None,
                )
            )
            nested.commit()
            source_count += 1
        except IntegrityError:
            nested.rollback()
            logger.warning("Source URL already exists in DB (duplicate hash): %s", canon)
    return source_count


def create_generated_post(
    *,
    topic: dict,
    proposal: dict | None = None,
    content: dict,
    strategy: dict,
    status: str = POST_STATUS_GENERATED,
) -> int:
    """
    Persist a generated carousel before publish attempt.
    """
    ensure_schema()
    created_at = _utc_now()
    topic_text = str(topic.get("topic", "")).strip()
    source_urls = topic.get("source_urls") or []
    if not isinstance(source_urls, list):
        source_urls = []

    with get_engine().begin() as conn:
        insert_result = conn.execute(
            posts_table.insert().values(
                ig_media_id=None,
                topic=topic_text or "(sin topic)",
                topic_en=str(topic.get("topic_en", "")).strip() or None,
                topic_hash=topic_hash(topic_text) or _hash_text(f"post-generated-{created_at.isoformat()}"),
                caption=str(strategy.get("full_caption") or content.get("caption") or "").strip() or None,
                virality_score=topic.get("virality_score"),
                status=status,
                ig_status="unknown",
                source_count=0,
                publish_attempts=0,
                published_at=None,
                topic_payload=topic,
                proposal_payload=proposal,
                content_payload=content,
                strategy_payload=strategy,
            )
        )
        post_id = int(insert_result.inserted_primary_key[0])
        source_count = _insert_post_sources(conn, post_id=post_id, source_urls=source_urls)
        conn.execute(posts_table.update().where(posts_table.c.id == post_id).values(source_count=source_count))
    return post_id


def create_draft_post(
    *,
    topic: dict,
    proposal: dict | None,
    content: dict,
    strategy: dict,
) -> int:
    """
    Persist a user-selected proposal as draft (ready to publish).
    """
    return create_generated_post(
        topic=topic,
        proposal=proposal,
        content=content,
        strategy=strategy,
        status=POST_STATUS_DRAFT,
    )


def mark_post_publish_attempt(post_id: int) -> None:
    """
    Increment publish attempts for a generated/failed post.
    """
    ensure_schema()
    with get_engine().begin() as conn:
        conn.execute(
            posts_table.update()
            .where(posts_table.c.id == int(post_id))
            .values(
                publish_attempts=(posts_table.c.publish_attempts + 1),
                last_publish_attempt_at=_utc_now(),
            )
        )


def mark_post_published(
    *,
    post_id: int,
    media_id: str,
    status: str = POST_STATUS_PUBLISHED_ACTIVE,
) -> None:
    ensure_schema()
    published_at = _utc_now()
    with get_engine().begin() as conn:
        conn.execute(
            posts_table.update()
            .where(posts_table.c.id == int(post_id))
            .values(
                ig_media_id=str(media_id).strip(),
                status=status,
                ig_status="active",
                ig_last_checked_at=published_at,
                published_at=published_at,
                last_error_tag=None,
                last_error_code=None,
                last_error_message=None,
            )
        )


def mark_post_publish_error(
    *,
    post_id: int,
    error_tag: str,
    error_code: str | None,
    error_message: str,
) -> None:
    ensure_schema()
    with get_engine().begin() as conn:
        conn.execute(
            posts_table.update()
            .where(posts_table.c.id == int(post_id))
            .values(
                status=POST_STATUS_PUBLISH_ERROR,
                last_error_tag=(error_tag or "publish_error"),
                last_error_code=(str(error_code).strip() if error_code else None),
                last_error_message=str(error_message or "").strip()[:2000] or None,
            )
        )


def mark_post_ig_active(*, post_id: int) -> None:
    ensure_schema()
    now = _utc_now()
    with get_engine().begin() as conn:
        conn.execute(
            posts_table.update()
            .where(posts_table.c.id == int(post_id))
            .values(
                status=POST_STATUS_PUBLISHED_ACTIVE,
                ig_status="active",
                ig_last_checked_at=now,
            )
        )


def mark_post_ig_deleted(*, post_id: int, reason: str | None = None) -> None:
    ensure_schema()
    now = _utc_now()
    with get_engine().begin() as conn:
        conn.execute(
            posts_table.update()
            .where(posts_table.c.id == int(post_id))
            .values(
                status=POST_STATUS_PUBLISHED_DELETED,
                ig_status="deleted",
                ig_last_checked_at=now,
                last_error_tag="ig_deleted",
                last_error_code="100:33",
                last_error_message=(str(reason or "").strip()[:2000] or None),
            )
        )


def get_post(post_id: int) -> dict | None:
    ensure_schema()
    safe_post_id = int(post_id)
    with get_engine().begin() as conn:
        row = (
            conn.execute(
                select(
                    posts_table.c.id,
                    posts_table.c.ig_media_id,
                    posts_table.c.topic,
                    posts_table.c.caption,
                    posts_table.c.virality_score,
                    posts_table.c.topic_payload,
                    posts_table.c.proposal_payload,
                    posts_table.c.content_payload,
                    posts_table.c.strategy_payload,
                    posts_table.c.status,
                    posts_table.c.ig_status,
                    posts_table.c.source_count,
                    posts_table.c.publish_attempts,
                    posts_table.c.last_error_tag,
                    posts_table.c.last_error_code,
                    posts_table.c.last_error_message,
                    posts_table.c.last_publish_attempt_at,
                    posts_table.c.ig_last_checked_at,
                    posts_table.c.published_at,
                    posts_table.c.created_at,
                )
                .where(posts_table.c.id == safe_post_id)
                .limit(1)
            )
            .mappings()
            .first()
        )
        if not row:
            return None

        src_rows = (
            conn.execute(
                select(post_sources_table.c.source_url)
                .where(post_sources_table.c.post_id == safe_post_id)
                .order_by(post_sources_table.c.id.asc())
            )
            .mappings()
            .all()
        )

        metric_row = (
            conn.execute(
                select(
                    post_metrics_table.c.collected_at,
                    post_metrics_table.c.impressions,
                    post_metrics_table.c.reach,
                    post_metrics_table.c.likes,
                    post_metrics_table.c.comments,
                    post_metrics_table.c.saves,
                    post_metrics_table.c.shares,
                    post_metrics_table.c.engagement_rate,
                )
                .where(post_metrics_table.c.post_id == safe_post_id)
                .order_by(post_metrics_table.c.collected_at.desc(), post_metrics_table.c.id.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )

    out = dict(row)
    history_slides, history_preview_slides = _extract_history_slide_refs(out.get("content_payload"))
    for key in ("last_publish_attempt_at", "ig_last_checked_at", "published_at", "created_at"):
        value = out.get(key)
        if isinstance(value, datetime):
            out[key] = value.isoformat()

    out["source_urls"] = [r["source_url"] for r in src_rows]
    out["history_slides"] = history_slides
    out["history_preview_slides"] = history_preview_slides
    if metric_row:
        out["metrics"] = {
            "collected_at": metric_row["collected_at"].isoformat() if metric_row["collected_at"] else None,
            "impressions": metric_row["impressions"],
            "reach": metric_row["reach"],
            "likes": metric_row["likes"],
            "comments": metric_row["comments"],
            "saves": metric_row["saves"],
            "shares": metric_row["shares"],
            "engagement_rate": metric_row["engagement_rate"],
        }
    else:
        out["metrics"] = None
    return out


def list_retryable_posts(limit: int = 20) -> list[dict]:
    ensure_schema()
    safe_limit = max(1, min(int(limit or 20), 200))
    with get_engine().begin() as conn:
        rows = (
            conn.execute(
                select(
                    posts_table.c.id,
                    posts_table.c.topic,
                    posts_table.c.status,
                    posts_table.c.publish_attempts,
                    posts_table.c.last_error_tag,
                    posts_table.c.last_error_message,
                    posts_table.c.created_at,
                )
                .where(posts_table.c.status.in_(list(RETRYABLE_STATUSES)))
                .order_by(posts_table.c.created_at.desc(), posts_table.c.id.desc())
                .limit(safe_limit)
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]


def list_pending_posts_for_ig_reconcile(
    *,
    limit: int = 40,
    max_age_hours: int = 72,
) -> list[dict]:
    """
    Return recent posts that are still retryable and missing IG media id.

    These are candidates for reconciliation when Instagram actually published
    the post but local DB status was not updated.
    """
    ensure_schema()
    safe_limit = max(1, min(int(limit or 40), 200))
    safe_hours = max(1, min(int(max_age_hours or 72), 24 * 30))
    cutoff = _utc_now() - timedelta(hours=safe_hours)

    with get_engine().begin() as conn:
        rows = (
            conn.execute(
                select(
                    posts_table.c.id,
                    posts_table.c.topic,
                    posts_table.c.caption,
                    posts_table.c.status,
                    posts_table.c.publish_attempts,
                    posts_table.c.created_at,
                    posts_table.c.last_publish_attempt_at,
                )
                .where(posts_table.c.status.in_(list(RETRYABLE_STATUSES)))
                .where((posts_table.c.ig_media_id.is_(None)) | (posts_table.c.ig_media_id == ""))
                .where(posts_table.c.caption.is_not(None))
                .where(posts_table.c.caption != "")
                .where(posts_table.c.created_at >= cutoff)
                .order_by(posts_table.c.created_at.desc(), posts_table.c.id.desc())
                .limit(safe_limit)
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]


def save_published_post(
    media_id: str,
    topic: dict,
    content: dict,
    strategy: dict,
    *,
    status: str = POST_STATUS_PUBLISHED_ACTIVE,
) -> int:
    """
    Backward-compatible helper used by legacy paths and migration scripts.
    """
    post_id = create_generated_post(
        topic=topic,
        content=content,
        strategy=strategy,
        status=POST_STATUS_GENERATED,
    )
    mark_post_publish_attempt(post_id)
    mark_post_published(post_id=post_id, media_id=media_id, status=status)
    return int(post_id)


def _topic_from_caption_for_import(caption: str | None, media_id: str) -> str:
    text = str(caption or "").strip()
    if not text:
        return f"IG import {media_id}"
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    topic = first_line or text
    return topic[:180]


def upsert_imported_ig_post(
    *,
    media_id: str,
    caption: str | None = None,
    media_timestamp=None,
    media_type: str | None = None,
    permalink: str | None = None,
) -> tuple[int, bool]:
    """
    Ensure one local post row exists for a published IG media id.

    Returns:
      (post_id, created_new)
    """
    ensure_schema()
    safe_media_id = str(media_id or "").strip()
    if not safe_media_id:
        raise ValueError("media_id is required")

    published_at = _parse_maybe_datetime(media_timestamp) or _utc_now()
    topic = _topic_from_caption_for_import(caption, safe_media_id)
    payload = {
        "imported_from_ig": True,
        "media_id": safe_media_id,
        "media_type": str(media_type or "").strip() or None,
        "permalink": str(permalink or "").strip() or None,
        "timestamp": published_at.isoformat(),
    }

    with get_engine().begin() as conn:
        existing = (
            conn.execute(select(posts_table.c.id).where(posts_table.c.ig_media_id == safe_media_id).limit(1))
            .mappings()
            .first()
        )
        if existing:
            post_id = int(existing["id"])
            conn.execute(
                update(posts_table)
                .where(posts_table.c.id == post_id)
                .values(
                    status=POST_STATUS_PUBLISHED_ACTIVE,
                    ig_status="active",
                    ig_last_checked_at=_utc_now(),
                )
            )
            return post_id, False

        result = conn.execute(
            posts_table.insert().values(
                ig_media_id=safe_media_id,
                topic=topic,
                topic_en=None,
                topic_hash=topic_hash(topic) or _hash_text(f"imported-{safe_media_id}"),
                caption=str(caption or "").strip() or None,
                virality_score=None,
                status=POST_STATUS_PUBLISHED_ACTIVE,
                ig_status="active",
                source_count=0,
                publish_attempts=0,
                last_publish_attempt_at=None,
                last_error_tag=None,
                last_error_code=None,
                last_error_message=None,
                ig_last_checked_at=_utc_now(),
                published_at=published_at,
                topic_payload=payload,
                proposal_payload=None,
                content_payload=None,
                strategy_payload=None,
            )
        )
        return int(result.inserted_primary_key[0]), True


def list_posts_for_metrics_sync(limit: int = 50) -> list[dict]:
    """
    Return published posts with IG media id, newest first.
    Useful as source set for metrics synchronization jobs.
    """
    ensure_schema()
    safe_limit = max(1, min(int(limit or 50), 500))
    with get_engine().begin() as conn:
        rows = (
            conn.execute(
                select(
                    posts_table.c.id,
                    posts_table.c.ig_media_id,
                    posts_table.c.topic,
                    posts_table.c.published_at,
                    posts_table.c.status,
                    posts_table.c.ig_status,
                )
                .where(posts_table.c.status.in_(list(PUBLISHED_STATUSES)))
                .where(posts_table.c.ig_media_id.is_not(None))
                .where(posts_table.c.ig_media_id != "")
                .order_by(posts_table.c.published_at.desc(), posts_table.c.id.desc())
                .limit(safe_limit)
            )
            .mappings()
            .all()
        )
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
        row = (
            conn.execute(select(posts_table.c.id).where(posts_table.c.ig_media_id == media_id).limit(1))
            .mappings()
            .first()
        )
    if not row:
        return None

    return save_metrics_snapshot(
        post_id=int(row["id"]),
        metrics=metrics,
        raw_payload=raw_payload,
        collected_at=collected_at,
    )


def mark_post_ig_deleted_by_media_id(ig_media_id: str, *, reason: str | None = None) -> bool:
    ensure_schema()
    media_id = str(ig_media_id or "").strip()
    if not media_id:
        return False
    with get_engine().begin() as conn:
        row = (
            conn.execute(select(posts_table.c.id).where(posts_table.c.ig_media_id == media_id).limit(1))
            .mappings()
            .first()
        )
    if not row:
        return False
    mark_post_ig_deleted(post_id=int(row["id"]), reason=reason)
    return True


def mark_post_ig_active_by_media_id(ig_media_id: str) -> bool:
    ensure_schema()
    media_id = str(ig_media_id or "").strip()
    if not media_id:
        return False
    with get_engine().begin() as conn:
        row = (
            conn.execute(select(posts_table.c.id).where(posts_table.c.ig_media_id == media_id).limit(1))
            .mappings()
            .first()
        )
    if not row:
        return False
    mark_post_ig_active(post_id=int(row["id"]))
    return True


def list_posts(limit: int = 50) -> list[dict]:
    ensure_schema()
    safe_limit = max(1, min(int(limit or 50), 200))
    with get_engine().begin() as conn:
        post_rows = (
            conn.execute(
                select(
                    posts_table.c.id,
                    posts_table.c.ig_media_id,
                    posts_table.c.topic,
                    posts_table.c.content_payload,
                    posts_table.c.virality_score,
                    posts_table.c.status,
                    posts_table.c.ig_status,
                    posts_table.c.source_count,
                    posts_table.c.publish_attempts,
                    posts_table.c.last_publish_attempt_at,
                    posts_table.c.last_error_tag,
                    posts_table.c.last_error_code,
                    posts_table.c.last_error_message,
                    posts_table.c.ig_last_checked_at,
                    posts_table.c.published_at,
                    posts_table.c.created_at,
                )
                .order_by(posts_table.c.created_at.desc(), posts_table.c.id.desc())
                .limit(safe_limit)
            )
            .mappings()
            .all()
        )
        if not post_rows:
            return []

        post_ids = [row["id"] for row in post_rows]
        src_rows = (
            conn.execute(
                select(post_sources_table.c.post_id, post_sources_table.c.source_url)
                .where(post_sources_table.c.post_id.in_(post_ids))
                .order_by(post_sources_table.c.id.asc())
            )
            .mappings()
            .all()
        )
        metric_rows = (
            conn.execute(
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
            )
            .mappings()
            .all()
        )

    sources_by_post = {}
    for row in src_rows:
        sources_by_post.setdefault(row["post_id"], []).append(row["source_url"])

    latest_metrics_by_post = {}
    for row in metric_rows:
        post_id = row["post_id"]
        if post_id in latest_metrics_by_post:
            continue
        latest_metrics_by_post[post_id] = {
            "metrics_collected_at": (row["collected_at"].isoformat() if row["collected_at"] else None),
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
        created_at = row["created_at"]
        last_publish_attempt_at = row["last_publish_attempt_at"]
        ig_last_checked_at = row["ig_last_checked_at"]
        metrics = latest_metrics_by_post.get(row["id"], {})
        history_slides, history_preview_slides = _extract_history_slide_refs(row.get("content_payload"))
        out.append(
            {
                "id": row["id"],
                "ig_media_id": row["ig_media_id"],
                "topic": row["topic"],
                "status": row["status"],
                "ig_status": row["ig_status"],
                "virality_score": row["virality_score"],
                "source_count": row["source_count"],
                "publish_attempts": row["publish_attempts"],
                "last_publish_attempt_at": (last_publish_attempt_at.isoformat() if last_publish_attempt_at else None),
                "last_error_tag": row["last_error_tag"],
                "last_error_code": row["last_error_code"],
                "last_error_message": row["last_error_message"],
                "ig_last_checked_at": (ig_last_checked_at.isoformat() if ig_last_checked_at else None),
                "published_at": published_at.isoformat() if published_at else None,
                "created_at": created_at.isoformat() if created_at else None,
                "source_urls": sources_by_post.get(row["id"], []),
                "history_slides": history_slides,
                "history_preview_slides": history_preview_slides,
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


# ---------------------------------------------------------------------------
# Rate-limit tracking (rolling 24 h window)
# ---------------------------------------------------------------------------

INSTAGRAM_DAILY_PUBLISH_LIMIT = 25


def count_recent_publishes(hours: int = 24) -> dict:
    """Count all API publish attempts in the last *hours* to track Instagram's
    ~25 posts/day rolling rate limit.  Meta counts every container-create call,
    even if it failed (error 2207032, timeouts, etc.), so we include
    publish_error posts that have at least one attempt."""
    ensure_schema()
    now_utc = datetime.now(UTC)
    cutoff = now_utc - timedelta(hours=hours)
    # Naive cutoff for columns stored without tz info
    cutoff_naive = cutoff.replace(tzinfo=None)

    def _to_utc(dt: datetime) -> datetime:
        """Ensure a datetime is timezone-aware (UTC)."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

    with get_engine().begin() as conn:
        # 1) Posts that were actually published (have published_at)
        published_rows = (
            conn.execute(
                select(posts_table.c.published_at)
                .where(
                    posts_table.c.published_at >= cutoff,
                    posts_table.c.status.in_(
                        {
                            POST_STATUS_PUBLISHED,
                            POST_STATUS_PUBLISHED_ACTIVE,
                            POST_STATUS_PUBLISHED_DELETED,
                        }
                    ),
                )
                .order_by(posts_table.c.published_at.asc())
            )
            .mappings()
            .all()
        )

        # 2) Failed attempts that Meta still counted against the limit
        error_rows = (
            conn.execute(
                select(posts_table.c.last_publish_attempt_at)
                .where(
                    posts_table.c.last_publish_attempt_at >= cutoff_naive,
                    posts_table.c.status == POST_STATUS_PUBLISH_ERROR,
                    posts_table.c.publish_attempts > 0,
                )
                .order_by(posts_table.c.last_publish_attempt_at.asc())
            )
            .mappings()
            .all()
        )

    # Merge all timestamps (normalized to UTC) to find the oldest
    all_timestamps: list[datetime] = []
    for r in published_rows:
        if r["published_at"] is not None:
            all_timestamps.append(_to_utc(r["published_at"]))
    for r in error_rows:
        if r["last_publish_attempt_at"] is not None:
            all_timestamps.append(_to_utc(r["last_publish_attempt_at"]))
    all_timestamps.sort()

    count = len(all_timestamps)
    oldest_published_at = None
    next_slot_in_minutes = None

    if all_timestamps:
        oldest = all_timestamps[0]
        oldest_published_at = oldest.isoformat()
        slot_free_at = oldest + timedelta(hours=hours)
        remaining = (slot_free_at - now_utc).total_seconds()
        next_slot_in_minutes = max(0, round(remaining / 60))

    return {
        "count": count,
        "limit": INSTAGRAM_DAILY_PUBLISH_LIMIT,
        "hours": hours,
        "oldest_published_at": oldest_published_at,
        "next_slot_in_minutes": next_slot_in_minutes,
    }


# ---------------------------------------------------------------------------
# Scheduler config CRUD
# ---------------------------------------------------------------------------


def get_scheduler_config() -> dict:
    ensure_schema()
    with get_engine().begin() as conn:
        row = (
            conn.execute(
                select(
                    scheduler_config_table.c.enabled,
                    scheduler_config_table.c.schedule,
                    scheduler_config_table.c.updated_at,
                )
                .order_by(scheduler_config_table.c.id.asc())
                .limit(1)
            )
            .mappings()
            .first()
        )
    if not row:
        return {"enabled": False, "schedule": _normalize_schedule(DEFAULT_SCHEDULE)}
    schedule = row["schedule"]
    if isinstance(schedule, str):
        schedule = json.loads(schedule)
    return {
        "enabled": bool(row["enabled"]),
        "schedule": _normalize_schedule(schedule),
    }


def save_scheduler_config(enabled: bool, schedule: dict) -> None:
    ensure_schema()
    now = _utc_now()
    normalized_schedule = _normalize_schedule(schedule)
    with get_engine().begin() as conn:
        existing = (
            conn.execute(select(scheduler_config_table.c.id).order_by(scheduler_config_table.c.id.asc()).limit(1))
            .mappings()
            .first()
        )
        if existing:
            conn.execute(
                update(scheduler_config_table)
                .where(scheduler_config_table.c.id == existing["id"])
                .values(enabled=int(enabled), schedule=normalized_schedule, updated_at=now)
            )
        else:
            conn.execute(
                scheduler_config_table.insert().values(enabled=int(enabled), schedule=normalized_schedule, updated_at=now)
            )


# ---------------------------------------------------------------------------
# Content queue CRUD
# ---------------------------------------------------------------------------


def _queue_row_to_dict(row) -> dict:
    d = dict(row)
    d["runs_total"] = max(1, _to_int(d.get("runs_total")) or 1)
    d["runs_completed"] = max(0, min(_to_int(d.get("runs_completed")) or 0, d["runs_total"]))
    for key in ("created_at", "started_at", "completed_at"):
        val = d.get(key)
        if isinstance(val, datetime):
            d[key] = val.isoformat()
    return d


def get_queue_items(days_back: int = 3, days_forward: int = 14) -> list[dict]:
    ensure_schema()
    from zoneinfo import ZoneInfo

    from config.settings import TIMEZONE

    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    start = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end = (now + timedelta(days=days_forward)).strftime("%Y-%m-%d")
    with get_engine().begin() as conn:
        rows = (
            conn.execute(
                select(content_queue_table)
                .where(content_queue_table.c.scheduled_date >= start)
                .where(content_queue_table.c.scheduled_date <= end)
                .order_by(content_queue_table.c.scheduled_date.asc())
            )
            .mappings()
            .all()
        )
    return [_queue_row_to_dict(r) for r in rows]


def get_queue_item_for_date(date_str: str) -> dict | None:
    ensure_schema()
    with get_engine().begin() as conn:
        row = (
            conn.execute(select(content_queue_table).where(content_queue_table.c.scheduled_date == date_str).limit(1))
            .mappings()
            .first()
        )
    return _queue_row_to_dict(row) if row else None


def add_queue_item(
    scheduled_date: str,
    topic: str | None = None,
    template: int | None = None,
    scheduled_time: str | None = None,
    runs_total: int = 1,
) -> int:
    ensure_schema()
    safe_runs_total = _normalize_posts_per_day(runs_total)
    with get_engine().begin() as conn:
        result = conn.execute(
            content_queue_table.insert().values(
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                topic=topic,
                template=template,
                status="pending",
                runs_total=safe_runs_total,
                runs_completed=0,
            )
        )
    return int(result.inserted_primary_key[0])


def remove_queue_item(item_id: int) -> bool:
    ensure_schema()
    with get_engine().begin() as conn:
        row = (
            conn.execute(select(content_queue_table.c.status).where(content_queue_table.c.id == int(item_id)).limit(1))
            .mappings()
            .first()
        )
        if not row or row["status"] != "pending":
            return False
        conn.execute(delete(content_queue_table).where(content_queue_table.c.id == int(item_id)))
    return True


def auto_fill_queue(days: int = 7) -> dict:
    ensure_schema()
    config = get_scheduler_config()
    schedule = config.get("schedule", DEFAULT_SCHEDULE)

    from zoneinfo import ZoneInfo

    from config.settings import TIMEZONE

    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz).date()

    created = []
    skipped_existing = 0
    skipped_disabled = 0

    for offset in range(days):
        d = today + timedelta(days=offset)
        date_str = d.strftime("%Y-%m-%d")
        day_name = DAY_NAMES[d.weekday()]
        day_cfg = schedule.get(day_name, {})

        if not day_cfg.get("enabled", False):
            skipped_disabled += 1
            continue

        existing = get_queue_item_for_date(date_str)
        if existing:
            skipped_existing += 1
            continue

        posts_per_day = _normalize_posts_per_day(day_cfg.get("posts_per_day", SCHEDULER_MIN_POSTS_PER_DAY))
        time_slots = resolve_day_schedule_times(day_cfg)
        time_str = time_slots[0] if time_slots else day_cfg.get("time")
        item_id = add_queue_item(
            scheduled_date=date_str,
            scheduled_time=time_str,
            runs_total=posts_per_day,
        )
        created.append(
            {
                "id": item_id,
                "scheduled_date": date_str,
                "scheduled_time": time_str,
                "runs_total": posts_per_day,
            }
        )

    return {
        "created": created,
        "skipped_existing": skipped_existing,
        "skipped_disabled": skipped_disabled,
    }


def mark_queue_item_processing(item_id: int) -> None:
    ensure_schema()
    with get_engine().begin() as conn:
        conn.execute(
            update(content_queue_table)
            .where(content_queue_table.c.id == int(item_id))
            .values(status="processing", started_at=_utc_now())
        )


def mark_queue_item_pending(
    item_id: int,
    *,
    runs_completed: int,
    runs_total: int,
    post_id: int | None = None,
    message: str | None = None,
) -> None:
    ensure_schema()
    safe_runs_total = _normalize_posts_per_day(runs_total)
    safe_runs_completed = max(0, min(_to_int(runs_completed) or 0, safe_runs_total))
    with get_engine().begin() as conn:
        conn.execute(
            update(content_queue_table)
            .where(content_queue_table.c.id == int(item_id))
            .values(
                status="pending",
                runs_completed=safe_runs_completed,
                runs_total=safe_runs_total,
                post_id=post_id,
                result_message=(message or "")[:2000] or None,
                started_at=None,
            )
        )


def mark_queue_item_completed(
    item_id: int,
    post_id: int | None = None,
    message: str | None = None,
    runs_total: int | None = None,
) -> None:
    ensure_schema()
    safe_runs_total = _normalize_posts_per_day(runs_total or 1)
    if runs_total is None:
        with get_engine().begin() as conn:
            row = (
                conn.execute(
                    select(content_queue_table.c.runs_total).where(content_queue_table.c.id == int(item_id)).limit(1)
                )
                .mappings()
                .first()
            )
            if row:
                safe_runs_total = _normalize_posts_per_day(row.get("runs_total"))
    with get_engine().begin() as conn:
        conn.execute(
            update(content_queue_table)
            .where(content_queue_table.c.id == int(item_id))
            .values(
                status="completed",
                runs_completed=safe_runs_total,
                runs_total=safe_runs_total,
                post_id=post_id,
                result_message=message,
                completed_at=_utc_now(),
            )
        )


def mark_queue_item_error(item_id: int, message: str | None = None) -> None:
    ensure_schema()
    with get_engine().begin() as conn:
        conn.execute(
            update(content_queue_table)
            .where(content_queue_table.c.id == int(item_id))
            .values(
                status="error",
                result_message=(message or "")[:2000] or None,
                started_at=None,
                completed_at=_utc_now(),
            )
        )


def get_last_used_template_name() -> str | None:
    """Return the template name from the most recent post's content_payload."""
    ensure_schema()
    with get_engine().begin() as conn:
        row = (
            conn.execute(
                select(posts_table.c.content_payload)
                .where(posts_table.c.content_payload.is_not(None))
                .order_by(posts_table.c.created_at.desc(), posts_table.c.id.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
    if not row:
        return None
    payload = row["content_payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, dict):
        return payload.get("template_name")
    return None


def recover_stale_processing(max_age_hours: int = 2) -> int:
    ensure_schema()
    cutoff = _utc_now() - timedelta(hours=max_age_hours)
    with get_engine().begin() as conn:
        result = conn.execute(
            update(content_queue_table)
            .where(content_queue_table.c.status == "processing")
            .where(content_queue_table.c.started_at < cutoff)
            .values(status="pending", started_at=None)
        )
    return result.rowcount
