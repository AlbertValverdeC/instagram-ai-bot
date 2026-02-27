"""
Scheduler daemon — auto-publishes content at configured times.

Runs as a daemon thread started from create_app(). Ticks every 60 seconds,
checks if conditions are met (enabled, correct day/time, pending item, pipeline
not running) and fires run_pipeline("live", ...).
"""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime

from flask import Flask

logger = logging.getLogger(__name__)

_scheduler_lock = threading.Lock()


def start_scheduler_daemon(app: Flask) -> None:
    """Spawn the background scheduler thread (called once from create_app)."""

    def _loop() -> None:
        with app.app_context():
            # Small initial delay to let the app fully start
            time.sleep(5)
            while True:
                try:
                    _scheduler_tick()
                except Exception as e:
                    logger.error("Scheduler tick error: %s", e, exc_info=True)
                time.sleep(60)

    t = threading.Thread(target=_loop, daemon=True, name="scheduler")
    t.start()
    logger.info("Scheduler daemon started")


def _scheduler_tick() -> None:
    from zoneinfo import ZoneInfo

    from config.settings import TIMEZONE
    from dashboard.services.pipeline_runner import (
        get_state_snapshot,
        is_running,
        run_pipeline,
        set_running,
    )
    from modules.post_store import (
        DAY_NAMES,
        SCHEDULER_MAX_POSTS_PER_DAY,
        SCHEDULER_MIN_POSTS_PER_DAY,
        get_queue_item_for_date,
        get_scheduler_config,
        mark_queue_item_completed,
        mark_queue_item_error,
        mark_queue_item_processing,
        recover_stale_processing,
    )

    config = get_scheduler_config()
    if not config["enabled"]:
        return

    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    day_name = DAY_NAMES[now.weekday()]
    today_str = now.strftime("%Y-%m-%d")

    schedule = config.get("schedule", {})
    day_cfg = schedule.get(day_name, {})
    if not day_cfg.get("enabled", False):
        return

    scheduled_time = day_cfg.get("time")
    if not scheduled_time:
        return

    # Check if we've passed the scheduled time
    match = re.match(r"^(\d{2}):(\d{2})$", scheduled_time)
    if not match:
        return
    sched_hour, sched_min = int(match.group(1)), int(match.group(2))
    if now.hour < sched_hour or (now.hour == sched_hour and now.minute < sched_min):
        return

    # Recover any stale processing items
    recovered = recover_stale_processing(2)
    if recovered:
        logger.info("Scheduler recovered %d stale processing items", recovered)

    # Check if there's a pending item for today
    item = get_queue_item_for_date(today_str)
    if not item or item["status"] != "pending":
        return

    # Don't run if pipeline is already busy
    if is_running():
        return

    item_id = item["id"]
    topic = item.get("topic")
    template = item.get("template")
    raw_posts_per_day = day_cfg.get("posts_per_day", SCHEDULER_MIN_POSTS_PER_DAY)
    try:
        posts_per_day = int(raw_posts_per_day)
    except (TypeError, ValueError):
        posts_per_day = SCHEDULER_MIN_POSTS_PER_DAY
    posts_per_day = max(SCHEDULER_MIN_POSTS_PER_DAY, min(posts_per_day, SCHEDULER_MAX_POSTS_PER_DAY))
    # For manual queue items with a fixed topic, keep single execution by default.
    if topic:
        posts_per_day = 1

    with _scheduler_lock:
        # Double-check under lock
        if is_running():
            return

        logger.info(
            "Scheduler firing: item_id=%s date=%s topic=%s runs=%s",
            item_id,
            today_str,
            topic or "(auto)",
            posts_per_day,
        )
        mark_queue_item_processing(item_id)

    success_post_ids: list[int] = []
    last_error_msg: str | None = None

    # Run pipeline synchronously (in this thread)
    for run_idx in range(posts_per_day):
        set_running(f"auto-publish ({run_idx + 1}/{posts_per_day})")
        try:
            run_pipeline("live", template, topic)
        except Exception as e:
            logger.error("Scheduler pipeline exception (run %s/%s): %s", run_idx + 1, posts_per_day, e)

        snapshot = get_state_snapshot()
        if snapshot["status"] == "done":
            output = snapshot.get("output", "")
            id_matches = re.findall(r"Saved generated carousel to post store \(id=(\d+)", output)
            if id_matches:
                success_post_ids.append(int(id_matches[-1]))
            continue

        last_error_msg = snapshot.get("error_summary") or "Pipeline did not complete successfully"
        logger.warning(
            "Scheduler run failed: item_id=%s run=%s/%s error=%s",
            item_id,
            run_idx + 1,
            posts_per_day,
            last_error_msg,
        )
        break

    if last_error_msg:
        succeeded = len(success_post_ids)
        if succeeded > 0:
            error_msg = (
                f"Ejecución parcial: {succeeded}/{posts_per_day} publicaciones completadas. "
                f"Último error: {last_error_msg}"
            )
        else:
            error_msg = last_error_msg
        mark_queue_item_error(item_id, message=error_msg)
        logger.warning("Scheduler failed: item_id=%s error=%s", item_id, error_msg)
        return

    final_post_id = success_post_ids[-1] if success_post_ids else None
    success_message = f"Auto-published {len(success_post_ids)}/{posts_per_day}"
    mark_queue_item_completed(item_id, post_id=final_post_id, message=success_message)
    logger.info("Scheduler completed: item_id=%s post_id=%s runs=%s", item_id, final_post_id, posts_per_day)
