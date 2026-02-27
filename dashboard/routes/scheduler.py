"""
Scheduler API endpoints.

GET  /api/scheduler              — full state (config + queue + next_run)
POST /api/scheduler/config       — update config (enabled, schedule)
POST /api/scheduler/queue        — add item to content queue
DELETE /api/scheduler/queue/<id> — remove pending item
POST /api/scheduler/queue/auto-fill — auto-fill queue for N days
"""

from __future__ import annotations

import re
from datetime import datetime

from flask import Blueprint, jsonify, request

from dashboard.auth import require_api_token

bp = Blueprint("scheduler_routes", __name__)

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _compute_next_run(config: dict, queue: list[dict]) -> dict | None:
    """Find the next pending queue item on an enabled day."""
    if not config.get("enabled"):
        return None

    from zoneinfo import ZoneInfo

    from config.settings import TIMEZONE
    from modules.post_store import DAY_NAMES

    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    schedule = config.get("schedule", {})

    pending = [q for q in queue if q["status"] == "pending"]
    pending.sort(key=lambda q: q["scheduled_date"])

    for item in pending:
        try:
            d = datetime.strptime(item["scheduled_date"], "%Y-%m-%d").date()
        except ValueError:
            continue

        day_name = DAY_NAMES[d.weekday()]
        day_cfg = schedule.get(day_name, {})
        if not day_cfg.get("enabled"):
            continue

        time_str = item.get("scheduled_time") or day_cfg.get("time") or "08:30"
        match = _TIME_RE.match(time_str)
        if not match:
            continue

        sched_dt = datetime(d.year, d.month, d.day, int(time_str[:2]), int(time_str[3:]), tzinfo=tz)
        if sched_dt < now:
            # Only skip if the date is in the past (not today — today might still fire)
            if d < now.date():
                continue

        diff = sched_dt - now
        hours_until = round(diff.total_seconds() / 3600, 1)

        return {
            "date": item["scheduled_date"],
            "time": time_str,
            "day_name": day_name,
            "topic": item.get("topic"),
            "hours_until": max(0, hours_until),
        }

    return None


@bp.get("/api/scheduler")
def get_scheduler():
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    from config.settings import TIMEZONE
    from dashboard.services.pipeline_runner import is_running
    from modules.post_store import get_queue_items, get_scheduler_config

    config = get_scheduler_config()
    queue = get_queue_items(days_back=3, days_forward=14)
    next_run = _compute_next_run(config, queue)

    return jsonify(
        {
            "config": config,
            "queue": queue,
            "next_run": next_run,
            "pipeline_running": is_running(),
            "timezone": TIMEZONE,
        }
    )


@bp.post("/api/scheduler/config")
def save_config():
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    from modules.post_store import (
        DAY_NAMES,
        SCHEDULER_MAX_POSTS_PER_DAY,
        SCHEDULER_MIN_POSTS_PER_DAY,
        save_scheduler_config,
    )

    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("enabled", False))
    schedule = data.get("schedule")

    if schedule:
        if not isinstance(schedule, dict):
            return jsonify({"error": "schedule must be an object"}), 400
        for day in DAY_NAMES:
            day_cfg = schedule.get(day)
            if not day_cfg:
                continue
            t = day_cfg.get("time")
            if t is not None and not _TIME_RE.match(str(t)):
                return jsonify({"error": f"Invalid time for {day}: {t}"}), 400
            posts_per_day = day_cfg.get("posts_per_day")
            if posts_per_day is not None:
                try:
                    posts_per_day_int = int(posts_per_day)
                except (TypeError, ValueError):
                    return jsonify({"error": f"Invalid posts_per_day for {day}: {posts_per_day}"}), 400
                if posts_per_day_int < SCHEDULER_MIN_POSTS_PER_DAY or posts_per_day_int > SCHEDULER_MAX_POSTS_PER_DAY:
                    return (
                        jsonify(
                            {
                                "error": (
                                    f"posts_per_day for {day} must be between "
                                    f"{SCHEDULER_MIN_POSTS_PER_DAY} and {SCHEDULER_MAX_POSTS_PER_DAY}"
                                )
                            }
                        ),
                        400,
                    )

    # Merge with current config if schedule not provided
    if not schedule:
        from modules.post_store import get_scheduler_config

        current = get_scheduler_config()
        schedule = current["schedule"]

    save_scheduler_config(enabled, schedule)
    return jsonify({"saved": True})


@bp.post("/api/scheduler/queue")
def add_queue():
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    from zoneinfo import ZoneInfo

    from config.settings import TIMEZONE
    from modules.post_store import DAY_NAMES, add_queue_item, get_scheduler_config

    data = request.get_json(silent=True) or {}
    scheduled_date = str(data.get("scheduled_date", "")).strip()
    topic = data.get("topic")
    template = data.get("template")
    scheduled_time = data.get("scheduled_time")

    if not scheduled_date or not _DATE_RE.match(scheduled_date):
        return jsonify({"error": "scheduled_date required (YYYY-MM-DD)"}), 400

    # Don't allow past dates
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    try:
        d = datetime.strptime(scheduled_date, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    if d < now.date():
        return jsonify({"error": "Cannot schedule for past dates"}), 400

    if scheduled_time and not _TIME_RE.match(str(scheduled_time)):
        return jsonify({"error": "Invalid time format (HH:MM)"}), 400

    # If no time provided, use config default for that day
    if not scheduled_time:
        config = get_scheduler_config()
        day_name = DAY_NAMES[d.weekday()]
        day_cfg = config.get("schedule", {}).get(day_name, {})
        scheduled_time = day_cfg.get("time")

    try:
        item_id = add_queue_item(
            scheduled_date=scheduled_date,
            topic=topic if topic else None,
            template=template,
            scheduled_time=scheduled_time,
        )
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return jsonify({"error": f"Already have an entry for {scheduled_date}"}), 409
        raise

    return jsonify({"id": item_id, "scheduled_date": scheduled_date}), 201


@bp.delete("/api/scheduler/queue/<int:item_id>")
def remove_queue(item_id: int):
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    from modules.post_store import remove_queue_item

    deleted = remove_queue_item(item_id)
    if not deleted:
        return jsonify({"error": "Item not found or not pending"}), 400

    return jsonify({"deleted": True})


@bp.post("/api/scheduler/queue/auto-fill")
def auto_fill():
    auth_error = require_api_token()
    if auth_error:
        return auth_error

    from modules.post_store import auto_fill_queue

    data = request.get_json(silent=True) or {}
    days = min(max(int(data.get("days", 7)), 1), 30)

    result = auto_fill_queue(days=days)
    return jsonify(result)
