from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time

from flask import current_app

from dashboard.config import PROJECT_ROOT

try:
    from modules.metrics_sync import sync_recent_post_metrics as db_sync_post_metrics
except Exception:
    db_sync_post_metrics = None


def _safe_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return int(str(raw).strip() or str(default))
    except Exception:
        return default


_AUTO_IG_SYNC_INTERVAL_MINUTES = max(0, _safe_int_env("AUTO_IG_SYNC_INTERVAL_MINUTES", 30))
_AUTO_IG_SYNC_LIMIT = max(1, min(_safe_int_env("AUTO_IG_SYNC_LIMIT", 40), 200))
_last_auto_ig_sync_at = 0.0
_auto_sync_lock = threading.Lock()


_lock = threading.Lock()
_state = {
    "status": "idle",
    "output": "",
    "error_summary": None,
    "started_at": None,
    "finished_at": None,
    "mode": None,
}


def get_lock() -> threading.Lock:
    return _lock


def get_state_snapshot() -> dict:
    with _lock:
        elapsed = None
        if _state["started_at"]:
            end = _state["finished_at"] or time.time()
            elapsed = round(end - _state["started_at"], 1)
        return {
            "status": _state["status"],
            "output": _state["output"],
            "error_summary": _state.get("error_summary"),
            "mode": _state["mode"],
            "elapsed": elapsed,
        }


def is_running() -> bool:
    with _lock:
        return _state["status"] == "running"


def set_running(mode_label: str) -> None:
    with _lock:
        _state["status"] = "running"
        _state["output"] = ""
        _state["error_summary"] = None
        _state["started_at"] = time.time()
        _state["finished_at"] = None
        _state["mode"] = mode_label


def pipeline_execution_mode() -> str:
    """
    Determine pipeline execution mode.

    - "sync": run in-request (reliable for Cloud Run lifecycle)
    - "thread": background thread (better local UX)
    """
    raw = (os.getenv("PIPELINE_EXECUTION_MODE") or "").strip().lower()
    if raw in {"sync", "thread"}:
        return raw
    if os.getenv("K_SERVICE"):
        return "sync"
    return "thread"


def _find_python() -> str:
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def extract_pipeline_error_summary(output: str) -> str | None:
    text = str(output or "")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    failure = None
    for ln in reversed(lines):
        if "Pipeline failed:" in ln:
            failure = ln.split("Pipeline failed:", 1)[1].strip()
            break
    if not failure:
        return None

    low = failure.lower()
    if "application request limit reached" in low or "subcode=2207051" in low:
        return "Meta aplicó límite temporal de peticiones. Espera unos minutos y reintenta."
    if "subcode=2207085" in low and "fatal" in low:
        return "Meta devolvió error fatal tras rate-limit. Reintenta más tarde."
    if "image url is not valid for instagram graph api" in low:
        return "Meta no puede leer las imágenes públicas. Revisa PUBLIC_IMAGE_BASE_URL."
    if "unauthorized" in low or "code=190" in low:
        return "Token/permisos de Meta inválidos o expirados."
    return failure[:240]


def classify_publish_error_text(raw_error: str) -> tuple[str, str, str | None]:
    text = str(raw_error or "").strip()
    low = text.lower()
    code = None
    code_match = re.search(r"code=([-]?\d+)", text)
    subcode_match = re.search(r"subcode=([0-9]+)", text)
    if code_match and subcode_match:
        code = f"{code_match.group(1)}:{subcode_match.group(1)}"
    elif code_match:
        code = code_match.group(1)
    elif subcode_match:
        code = subcode_match.group(1)

    if "application request limit reached" in low or "2207051" in text:
        return (
            "meta_rate_limit",
            "Meta aplicó límite temporal de peticiones. Espera unos minutos y reintenta.",
            code,
        )
    if "2207085" in text and "fatal" in low:
        return (
            "meta_fatal_after_limit",
            "Meta devolvió error fatal tras rate-limit. Reintenta más tarde.",
            code,
        )
    if "image url is not valid for instagram graph api" in low:
        return (
            "image_url_invalid",
            "Meta no puede acceder a las imágenes públicas. Revisa PUBLIC_IMAGE_BASE_URL.",
            code,
        )
    if "unauthorized" in low or "code=190" in text:
        return (
            "meta_auth",
            "Token/permisos de Meta inválidos o expirados.",
            code,
        )
    return ("publish_unknown", text[:220], code)


def maybe_auto_sync_instagram() -> None:
    global _last_auto_ig_sync_at
    if db_sync_post_metrics is None or _AUTO_IG_SYNC_INTERVAL_MINUTES <= 0:
        return

    now = time.time()
    with _auto_sync_lock:
        if (now - _last_auto_ig_sync_at) < (_AUTO_IG_SYNC_INTERVAL_MINUTES * 60):
            return
        _last_auto_ig_sync_at = now
    logger = current_app.logger

    def _runner():
        try:
            result = db_sync_post_metrics(limit=_AUTO_IG_SYNC_LIMIT)
            logger.info(
                "Auto IG sync done: checked=%s updated=%s failed=%s",
                result.get("checked"),
                result.get("updated"),
                result.get("failed"),
            )
        except Exception as e:
            logger.warning("Auto IG sync failed: %s", e)

    threading.Thread(target=_runner, daemon=True).start()


def run_pipeline(mode: str, template: int | None, topic: str | None = None, step: str | None = None):
    cmd = [_find_python(), str(PROJECT_ROOT / "main_pipeline.py")]
    if mode == "test":
        cmd.append("--test")
    elif mode == "dry-run":
        cmd.append("--dry-run")
    if template is not None:
        cmd.extend(["--template", str(template)])
    if step:
        cmd.extend(["--step", step])
    if topic:
        cmd.extend(["--topic", topic.strip()])

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        output_lines = []
        assert proc.stdout is not None
        for line in proc.stdout:
            output_lines.append(line)
            with _lock:
                _state["output"] = "".join(output_lines)
        proc.wait()
        with _lock:
            _state["output"] = "".join(output_lines)
            _state["status"] = "done" if proc.returncode == 0 else "error"
            _state["error_summary"] = (
                None if proc.returncode == 0 else extract_pipeline_error_summary(_state["output"])
            )
            _state["finished_at"] = time.time()
    except Exception as e:
        with _lock:
            _state["output"] += f"\n\nERROR: {e}"
            _state["status"] = "error"
            _state["error_summary"] = str(e)
            _state["finished_at"] = time.time()


def run_pipeline_sync(mode: str, template: int | None, topic: str | None = None, step: str | None = None) -> dict:
    run_pipeline(mode, template, topic, step)
    with _lock:
        elapsed = None
        if _state["started_at"]:
            elapsed = round((_state["finished_at"] or time.time()) - _state["started_at"], 1)
        return {
            "status": _state["status"],
            "mode": mode,
            "elapsed": elapsed,
            "error_summary": _state.get("error_summary"),
            "output_tail": (_state.get("output") or "")[-1200:],
        }


def run_pipeline_thread(mode: str, template: int | None, topic: str | None = None, step: str | None = None) -> None:
    thread = threading.Thread(target=run_pipeline, args=(mode, template, topic, step), daemon=True)
    thread.start()


def get_auto_sync_interval_minutes() -> int:
    return _AUTO_IG_SYNC_INTERVAL_MINUTES
