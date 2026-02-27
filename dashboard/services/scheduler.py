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
        mark_queue_item_pending,
        mark_queue_item_processing,
        recover_stale_processing,
        resolve_day_schedule_times,
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

    time_slots = resolve_day_schedule_times(day_cfg)
    if not time_slots:
        return

    # Recover any stale processing items
    recovered = recover_stale_processing(2)
    if recovered:
        logger.info("Scheduler recovered %d stale processing items", recovered)

    # Check if there's a pending item for today
    item = get_queue_item_for_date(today_str)
    if not item or item["status"] not in {"pending", "processing"}:
        return

    item_id = item["id"]
    topic = item.get("topic")
    template = item.get("template")
    now_hhmm = now.strftime("%H:%M")

    if topic:
        manual_time = str(item.get("scheduled_time") or day_cfg.get("time") or "").strip()
        if not manual_time:
            return
        selected_slots = [manual_time]
    else:
        raw_posts_per_day = day_cfg.get("posts_per_day", SCHEDULER_MIN_POSTS_PER_DAY)
        try:
            posts_per_day = int(raw_posts_per_day)
        except (TypeError, ValueError):
            posts_per_day = SCHEDULER_MIN_POSTS_PER_DAY
        posts_per_day = max(SCHEDULER_MIN_POSTS_PER_DAY, min(posts_per_day, SCHEDULER_MAX_POSTS_PER_DAY))
        selected_slots = time_slots[:posts_per_day] if len(time_slots) >= posts_per_day else time_slots
        if not selected_slots:
            return

    runs_total = len(selected_slots)
    try:
        runs_completed = max(0, int(item.get("runs_completed") or 0))
    except (TypeError, ValueError):
        runs_completed = 0
    runs_completed = min(runs_completed, runs_total)

    due_runs = sum(1 for slot in selected_slots if slot <= now_hhmm)
    if due_runs <= 0:
        return
    if runs_completed >= runs_total:
        mark_queue_item_completed(
            item_id,
            post_id=item.get("post_id"),
            message=f"Auto-published {runs_total}/{runs_total}",
            runs_total=runs_total,
        )
        return
    if runs_completed >= due_runs:
        return

    # Don't run if pipeline is already busy
    if is_running():
        return

    with _scheduler_lock:
        # Double-check under lock
        if is_running():
            return

        current_run = runs_completed + 1
        current_slot = selected_slots[current_run - 1]
        logger.info(
            "Scheduler firing: item_id=%s date=%s topic=%s run=%s/%s slot=%s",
            item_id,
            today_str,
            topic or "(auto)",
            current_run,
            runs_total,
            current_slot,
        )
        mark_queue_item_processing(item_id)
    set_running(f"auto-publish ({current_run}/{runs_total})")

    # Run one due slot synchronously (in this thread)
    try:
        run_pipeline("live", template, topic)
    except Exception as e:
        logger.error("Scheduler pipeline exception (run %s/%s): %s", current_run, runs_total, e)

    snapshot = get_state_snapshot()
    if snapshot["status"] != "done":
        error_msg = snapshot.get("error_summary") or "Pipeline did not complete successfully"
        mark_queue_item_error(item_id, message=f"Falló publicación {current_run}/{runs_total}: {error_msg}")
        logger.warning("Scheduler failed: item_id=%s run=%s/%s error=%s", item_id, current_run, runs_total, error_msg)
        return

    post_id = None
    output = snapshot.get("output", "")
    id_matches = re.findall(r"Saved generated carousel to post store \(id=(\d+)", output)
    if id_matches:
        post_id = int(id_matches[-1])

    if current_run >= runs_total:
        success_message = f"Auto-published {runs_total}/{runs_total}"
        mark_queue_item_completed(item_id, post_id=post_id, message=success_message, runs_total=runs_total)
        logger.info("Scheduler completed: item_id=%s post_id=%s runs=%s", item_id, post_id, runs_total)
        return

    next_slot = selected_slots[current_run]
    mark_queue_item_pending(
        item_id,
        runs_completed=current_run,
        runs_total=runs_total,
        post_id=post_id,
        message=f"Publicado {current_run}/{runs_total}. Próxima hora: {next_slot}",
    )
    logger.info(
        "Scheduler partial success: item_id=%s run=%s/%s post_id=%s next_slot=%s",
        item_id,
        current_run,
        runs_total,
        post_id,
        next_slot,
    )
