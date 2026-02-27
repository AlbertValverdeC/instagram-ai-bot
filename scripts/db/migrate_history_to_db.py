#!/usr/bin/env python3
"""
Migrate legacy data/history.json into post_store database.

Usage:
  .venv/bin/python scripts/db/migrate_history_to_db.py
  .venv/bin/python scripts/db/migrate_history_to_db.py --dry-run
  .venv/bin/python scripts/db/migrate_history_to_db.py --history-file data/history.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.post_store import ensure_schema, get_engine, posts_table, topic_hash


def _parse_published_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _fallback_topic_hash(topic: str, media_id: str) -> str:
    return hashlib.sha256(f"{topic}|{media_id}".encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Migrate history.json to post_store DB")
    parser.add_argument(
        "--history-file",
        default="data/history.json",
        help="Path to history.json (default: data/history.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be inserted without writing DB",
    )
    args = parser.parse_args()

    history_path = Path(args.history_file)
    if not history_path.exists():
        raise SystemExit(f"history file not found: {history_path}")

    payload = json.loads(history_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit("history file must contain a JSON array")

    ensure_schema()
    engine = get_engine()

    total = len(payload)
    inserted = 0
    skipped_existing = 0
    skipped_invalid = 0

    with engine.begin() as conn:
        for row in payload:
            if not isinstance(row, dict):
                skipped_invalid += 1
                continue

            media_id = str(row.get("media_id") or "").strip()
            topic = str(row.get("topic") or "").strip()
            if not media_id or not topic:
                skipped_invalid += 1
                continue

            exists = (
                conn.execute(select(posts_table.c.id).where(posts_table.c.ig_media_id == media_id).limit(1))
                .mappings()
                .first()
            )
            if exists:
                skipped_existing += 1
                continue

            published_at = _parse_published_at(row.get("published_at"))
            values = dict(
                ig_media_id=media_id,
                topic=topic,
                topic_en=str(row.get("topic_en") or "").strip() or None,
                topic_hash=topic_hash(topic) or _fallback_topic_hash(topic, media_id),
                caption=None,
                virality_score=row.get("virality_score"),
                status="published_active",
                source_count=0,
                published_at=published_at,
                topic_payload=row,
                content_payload=None,
                strategy_payload=None,
            )
            if args.dry_run:
                print(f"[DRY-RUN] insert media_id={media_id} topic={topic[:80]}")
                inserted += 1
                continue

            conn.execute(posts_table.insert().values(**values))
            inserted += 1

    print(
        json.dumps(
            {
                "history_file": str(history_path),
                "total_rows": total,
                "inserted": inserted,
                "skipped_existing": skipped_existing,
                "skipped_invalid": skipped_invalid,
                "dry_run": args.dry_run,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
