#!/usr/bin/env python3
"""
Dashboard Web — Panel de control simple para Instagram AI Bot.

Usage:
    python dashboard.py              # http://localhost:5000
    python dashboard.py --port 8080  # http://localhost:8080
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output"
DATA_DIR = PROJECT_ROOT / "data"
PROMPTS_DIR = DATA_DIR / "prompts"
RESEARCH_CONFIG_FILE = DATA_DIR / "research_config.json"
ENV_FILE = PROJECT_ROOT / ".env"

# Ensure prompts dir exists
PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

# ── Prompts metadata ─────────────────────────────────────────────────────────

PROMPTS_CONFIG = [
    {
        "id": "research_meta",
        "name": "Meta-prompt investigacion",
        "description": "GPT-4o genera un prompt optimizado para que GPT-4o-mini seleccione el mejor tema del dia.",
        "category": "Investigacion",
        "type": "meta",
        "module": "prompt_director.py",
        "variables": ["day_name", "num_articles", "has_trends", "past_count"],
    },
    {
        "id": "research_fallback",
        "name": "Ranking de temas (fallback)",
        "description": "Prompt que analiza articulos y selecciona el mejor tema. Se usa si el Prompt Director falla.",
        "category": "Investigacion",
        "type": "fallback",
        "module": "researcher.py",
        "variables": ["articles_text", "trends_text", "past_text"],
    },
    {
        "id": "content_meta",
        "name": "Meta-prompt contenido",
        "description": "GPT-4o genera un prompt optimizado para crear contenido de carrusel viral.",
        "category": "Contenido",
        "type": "meta",
        "module": "prompt_director.py",
        "variables": ["topic_title", "topic_en", "key_points", "virality", "day_name", "tone_hint", "style_hint"],
    },
    {
        "id": "content_fallback",
        "name": "Generador de carrusel (fallback)",
        "description": "Prompt que genera los 8 slides del carrusel. Se usa si el Prompt Director falla.",
        "category": "Contenido",
        "type": "fallback",
        "module": "content_generator.py",
        "variables": ["topic", "key_points", "context", "total_slides", "num_content_slides"],
    },
    {
        "id": "image_meta",
        "name": "Meta-prompt imagen",
        "description": "GPT-4o genera un prompt de imagen optimizado para Imagen 4 basado en el tema.",
        "category": "Imagen",
        "type": "meta",
        "module": "prompt_director.py",
        "variables": ["topic_en"],
    },
    {
        "id": "image_fallback",
        "name": "Prompt imagen (fallback)",
        "description": "Prompt generico para el fondo del cover cuando Imagen 4 bloquea el prompt del Director.",
        "category": "Imagen",
        "type": "fallback",
        "module": "image_generator.py",
        "variables": [],
    },
]


def _get_prompt_defaults() -> dict:
    """Lazy-import all default prompts from modules."""
    from modules.prompt_director import (
        _DEFAULT_CONTENT_META,
        _DEFAULT_IMAGE_META,
        _DEFAULT_RESEARCH_META,
    )
    from modules.researcher import _DEFAULT_RESEARCH_FALLBACK
    from modules.content_generator import _DEFAULT_CONTENT_FALLBACK
    from modules.image_generator import _DEFAULT_IMAGE_FALLBACK

    return {
        "research_meta": _DEFAULT_RESEARCH_META,
        "research_fallback": _DEFAULT_RESEARCH_FALLBACK,
        "content_meta": _DEFAULT_CONTENT_META,
        "content_fallback": _DEFAULT_CONTENT_FALLBACK,
        "image_meta": _DEFAULT_IMAGE_META,
        "image_fallback": _DEFAULT_IMAGE_FALLBACK,
    }


# ── API Keys metadata ────────────────────────────────────────────────────────

API_KEYS_CONFIG = [
    {
        "key": "OPENAI_API_KEY",
        "label": "OpenAI API Key",
        "hint": "Clave para GPT-4o (Director) y GPT-4o-mini (Research + Content)",
        "placeholder": "sk-...",
        "required": True,
        "group": "AI Models",
        "url": "https://platform.openai.com/api-keys",
    },
    {
        "key": "GOOGLE_AI_API_KEY",
        "label": "Google AI API Key",
        "hint": "Gemini Imagen 3 para fondos AI del cover. Sin ella se usan degradados.",
        "placeholder": "AIza...",
        "required": False,
        "group": "AI Models",
        "url": "https://aistudio.google.com/apikey",
    },
    {
        "key": "DIRECTOR_MODEL",
        "label": "Director Model",
        "hint": "Modelo del Prompt Director. Por defecto gpt-4o.",
        "placeholder": "gpt-4o",
        "required": False,
        "group": "AI Models",
        "secret": False,
    },
    {
        "key": "NEWSAPI_KEY",
        "label": "NewsAPI Key",
        "hint": "Noticias tech de newsapi.org. Tier gratuito: 1.500 req/mes.",
        "placeholder": "",
        "required": True,
        "group": "Data Sources",
        "url": "https://newsapi.org/register",
    },
    {
        "key": "REDDIT_CLIENT_ID",
        "label": "Reddit Client ID",
        "hint": "Client ID de tu app Reddit (tipo script).",
        "placeholder": "",
        "required": False,
        "group": "Data Sources",
        "url": "https://www.reddit.com/prefs/apps",
    },
    {
        "key": "REDDIT_CLIENT_SECRET",
        "label": "Reddit Client Secret",
        "hint": "Client Secret de tu app Reddit.",
        "placeholder": "",
        "required": False,
        "group": "Data Sources",
    },
    {
        "key": "REDDIT_USER_AGENT",
        "label": "Reddit User Agent",
        "hint": "Identificador para la API de Reddit.",
        "placeholder": "instagram-ai-bot/1.0",
        "required": False,
        "group": "Data Sources",
        "secret": False,
    },
    {
        "key": "INSTAGRAM_ACCOUNT_ID",
        "label": "Instagram Account ID",
        "hint": "ID numérico de tu cuenta de Instagram Business.",
        "placeholder": "17841400000000000",
        "required": True,
        "group": "Publishing",
        "url": "https://developers.facebook.com/tools/explorer/",
        "secret": False,
    },
    {
        "key": "FACEBOOK_PAGE_ID",
        "label": "Facebook Page ID",
        "hint": "ID de la página de Facebook vinculada a tu cuenta de Instagram.",
        "placeholder": "000000000000000",
        "required": True,
        "group": "Publishing",
        "secret": False,
    },
    {
        "key": "META_ACCESS_TOKEN",
        "label": "Meta Access Token",
        "hint": "Token con permisos instagram_basic + instagram_content_publish.",
        "placeholder": "EAA...",
        "required": True,
        "group": "Publishing",
        "url": "https://developers.facebook.com/tools/explorer/",
    },
    {
        "key": "IMGUR_CLIENT_ID",
        "label": "Imgur Client ID",
        "hint": "Para hostear temporalmente las imágenes antes de publicar en Instagram.",
        "placeholder": "",
        "required": True,
        "group": "Publishing",
        "url": "https://api.imgur.com/oauth2/addclient",
    },
    {
        "key": "INSTAGRAM_HANDLE",
        "label": "Instagram Handle",
        "hint": "Tu @handle de Instagram. Aparece como watermark en los slides.",
        "placeholder": "@tu_cuenta_tech",
        "required": False,
        "group": "Branding",
        "secret": False,
    },
    {
        "key": "TIMEZONE",
        "label": "Timezone",
        "hint": "Zona horaria para calcular el horario óptimo de publicación.",
        "placeholder": "Europe/Madrid",
        "required": False,
        "group": "Branding",
        "secret": False,
    },
]


def _read_env() -> dict:
    """Read .env file and return key-value dict."""
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _write_env(updates: dict):
    """Update .env file, preserving comments and order. Adds new keys at the end."""
    lines = []
    existing_keys = set()

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k in updates:
                    lines.append(f"{k}={updates[k]}")
                    existing_keys.add(k)
                else:
                    lines.append(line)
            else:
                lines.append(line)

    # Append any new keys not already in the file
    for k, v in updates.items():
        if k not in existing_keys and v:
            lines.append(f"{k}={v}")

    ENV_FILE.write_text("\n".join(lines) + "\n")


def _mask_value(value: str, is_secret: bool = True) -> str:
    """Mask a secret value, showing only the last 4 chars."""
    if not is_secret or not value:
        return value
    if len(value) <= 6:
        return "***"
    return "***" + value[-4:]


# ── Pipeline state ───────────────────────────────────────────────────────────

_lock = threading.Lock()
_state = {
    "status": "idle",
    "output": "",
    "started_at": None,
    "finished_at": None,
    "mode": None,
}


def _find_python():
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _run_pipeline(mode: str, template: int | None):
    global _state
    cmd = [_find_python(), str(PROJECT_ROOT / "main_pipeline.py")]
    if mode == "test":
        cmd.append("--test")
    elif mode == "dry-run":
        cmd.append("--dry-run")
    if template is not None:
        cmd.extend(["--template", str(template)])

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        output_lines = []
        for line in proc.stdout:
            output_lines.append(line)
            with _lock:
                _state["output"] = "".join(output_lines)
        proc.wait()
        with _lock:
            _state["output"] = "".join(output_lines)
            _state["status"] = "done" if proc.returncode == 0 else "error"
            _state["finished_at"] = time.time()
    except Exception as e:
        with _lock:
            _state["output"] += f"\n\nERROR: {e}"
            _state["status"] = "error"
            _state["finished_at"] = time.time()


# ── API routes ───────────────────────────────────────────────────────────────

@app.route("/api/state")
def api_state():
    topic = None
    topic_file = DATA_DIR / "last_topic.json"
    if topic_file.exists():
        with open(topic_file) as f:
            topic = json.load(f)

    content = None
    content_file = DATA_DIR / "last_content.json"
    if content_file.exists():
        with open(content_file) as f:
            content = json.load(f)

    slides = sorted(f.name for f in OUTPUT_DIR.glob("slide_*.png"))

    history = []
    history_file = DATA_DIR / "history.json"
    if history_file.exists():
        with open(history_file) as f:
            history = json.load(f)

    return jsonify({
        "topic": topic,
        "content": content,
        "slides": slides,
        "history_count": len(history),
    })


@app.route("/api/run", methods=["POST"])
def api_run():
    with _lock:
        if _state["status"] == "running":
            return jsonify({"error": "Pipeline already running"}), 409

    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "test")
    if mode not in ("test", "dry-run", "live"):
        return jsonify({"error": f"Invalid mode: {mode}"}), 400

    template = data.get("template")
    if template is not None:
        template = int(template)

    with _lock:
        _state["status"] = "running"
        _state["output"] = ""
        _state["started_at"] = time.time()
        _state["finished_at"] = None
        _state["mode"] = mode

    thread = threading.Thread(target=_run_pipeline, args=(mode, template), daemon=True)
    thread.start()
    return jsonify({"status": "started", "mode": mode})


@app.route("/api/status")
def api_status():
    with _lock:
        elapsed = None
        if _state["started_at"]:
            end = _state["finished_at"] or time.time()
            elapsed = round(end - _state["started_at"], 1)
        return jsonify({
            "status": _state["status"],
            "output": _state["output"],
            "mode": _state["mode"],
            "elapsed": elapsed,
        })


@app.route("/api/keys", methods=["GET"])
def api_keys_get():
    """Return all API keys (masked) with their config metadata."""
    env = _read_env()
    keys = []
    for cfg in API_KEYS_CONFIG:
        is_secret = cfg.get("secret", True)
        raw = env.get(cfg["key"], "")
        keys.append({
            "key": cfg["key"],
            "label": cfg["label"],
            "hint": cfg["hint"],
            "placeholder": cfg["placeholder"],
            "required": cfg["required"],
            "group": cfg["group"],
            "url": cfg.get("url"),
            "secret": is_secret,
            "value": _mask_value(raw, is_secret) if is_secret else raw,
            "configured": bool(raw and raw != cfg["placeholder"]
                               and not raw.startswith("xxxxxxx")),
        })
    return jsonify(keys)


@app.route("/api/keys", methods=["POST"])
def api_keys_save():
    """Save API keys to .env file."""
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "No data"}), 400

    env = _read_env()
    updates = {}
    for k, v in data.items():
        # Skip masked values (user didn't change them)
        if v and v.startswith("***"):
            continue
        updates[k] = v

    if updates:
        # Merge with existing
        merged = {**env, **updates}
        # Remove keys with empty values
        merged = {k: v for k, v in merged.items() if v}
        _write_env(updates)

    return jsonify({"saved": len(updates)})


@app.route("/api/prompts", methods=["GET"])
def api_prompts_get():
    """Return all 6 prompts with metadata, current text, and custom flag."""
    defaults = _get_prompt_defaults()
    result = []
    for cfg in PROMPTS_CONFIG:
        pid = cfg["id"]
        custom_file = PROMPTS_DIR / f"{pid}.txt"
        is_custom = custom_file.exists()
        if is_custom:
            text = custom_file.read_text(encoding="utf-8")
        else:
            text = defaults.get(pid, "")
        result.append({
            **cfg,
            "text": text,
            "default_text": defaults.get(pid, ""),
            "custom": is_custom,
        })
    return jsonify(result)


@app.route("/api/prompts", methods=["POST"])
def api_prompts_save():
    """Save a custom prompt. Validates that required {variables} are present."""
    data = request.get_json(silent=True) or {}
    pid = data.get("id", "")
    text = data.get("text", "")

    if not pid or not text:
        return jsonify({"error": "Faltan campos: id, text"}), 400

    # Find config for this prompt
    cfg = next((c for c in PROMPTS_CONFIG if c["id"] == pid), None)
    if cfg is None:
        return jsonify({"error": f"Prompt desconocido: {pid}"}), 400

    # Validate that all required variables are present
    missing = []
    for var in cfg["variables"]:
        # Check for {var} but not {{var}} (literal braces)
        placeholder = "{" + var + "}"
        if placeholder not in text:
            missing.append(placeholder)

    if missing:
        return jsonify({
            "error": f"Variables requeridas no encontradas: {', '.join(missing)}",
            "missing": missing,
        }), 400

    # Save to file
    filepath = PROMPTS_DIR / f"{pid}.txt"
    filepath.write_text(text, encoding="utf-8")
    return jsonify({"saved": pid})


@app.route("/api/prompts/reset", methods=["POST"])
def api_prompts_reset():
    """Reset a prompt to its default (delete the custom .txt file)."""
    data = request.get_json(silent=True) or {}
    pid = data.get("id", "")

    if not pid:
        return jsonify({"error": "Falta campo: id"}), 400

    cfg = next((c for c in PROMPTS_CONFIG if c["id"] == pid), None)
    if cfg is None:
        return jsonify({"error": f"Prompt desconocido: {pid}"}), 400

    filepath = PROMPTS_DIR / f"{pid}.txt"
    if filepath.exists():
        filepath.unlink()

    return jsonify({"reset": pid})


# ── Research config defaults ──────────────────────────────────────────────────

_DEFAULT_RESEARCH_CONFIG = {
    "subreddits": ["artificial", "technology", "MachineLearning", "ChatGPT"],
    "rss_feeds": [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://feeds.arstechnica.com/arstechnica/index",
        "https://www.technologyreview.com/feed/",
    ],
    "trends_keywords": [
        "AI", "GPT", "robot", "tech", "app", "Google", "Apple", "Meta",
        "Microsoft", "Samsung", "Tesla", "chip", "quantum", "cyber",
        "cloud", "data", "neural", "OpenAI", "startup", "software",
    ],
    "newsapi_domains": "techcrunch.com,theverge.com,arstechnica.com,wired.com",
}


@app.route("/api/research-config", methods=["GET"])
def api_research_config_get():
    """Return current research config (custom or defaults)."""
    config = dict(_DEFAULT_RESEARCH_CONFIG)
    is_custom = RESEARCH_CONFIG_FILE.exists()
    if is_custom:
        try:
            with open(RESEARCH_CONFIG_FILE) as f:
                custom = json.load(f)
            for key in config:
                if key in custom:
                    config[key] = custom[key]
        except Exception:
            is_custom = False
    return jsonify({"config": config, "custom": is_custom, "defaults": _DEFAULT_RESEARCH_CONFIG})


@app.route("/api/research-config", methods=["POST"])
def api_research_config_save():
    """Save research config to JSON file."""
    data = request.get_json(silent=True) or {}
    config = data.get("config")
    if not config:
        return jsonify({"error": "Falta campo: config"}), 400

    # Validate structure
    for key in ["subreddits", "rss_feeds", "trends_keywords"]:
        if key in config and not isinstance(config[key], list):
            return jsonify({"error": f"{key} debe ser una lista"}), 400
        if key in config and len(config[key]) == 0:
            return jsonify({"error": f"{key} no puede estar vacio"}), 400

    if "newsapi_domains" in config and not isinstance(config["newsapi_domains"], str):
        return jsonify({"error": "newsapi_domains debe ser texto (dominios separados por coma)"}), 400

    RESEARCH_CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return jsonify({"saved": True})


@app.route("/api/research-config/reset", methods=["POST"])
def api_research_config_reset():
    """Reset research config to defaults (delete the JSON file)."""
    if RESEARCH_CONFIG_FILE.exists():
        RESEARCH_CONFIG_FILE.unlink()
    return jsonify({"reset": True})


@app.route("/slides/<path:filename>")
def serve_slide(filename):
    return send_from_directory(str(OUTPUT_DIR), filename)


# ── Dashboard HTML ───────────────────────────────────────────────────────────

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IG AI Bot — Panel de Control</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0a0f1a;--bg-card:#111827;--bg-code:#1a2236;
  --border:#1e293b;--text:#e2e8f0;--text-dim:#94a3b8;
  --accent:#00c8ff;--accent2:#c084fc;--green:#34d399;
  --orange:#fb923c;--red:#f87171;--radius:10px;
}
html{scroll-behavior:smooth}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  background:var(--bg);color:var(--text);line-height:1.6;
  min-height:100vh;padding:0;
}

/* Header */
.header{
  background:var(--bg-card);border-bottom:1px solid var(--border);
  padding:20px 32px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;
}
.header h1{font-size:22px;font-weight:700}
.header h1 span{color:var(--accent)}
.header .badge{
  font-size:11px;padding:3px 10px;border-radius:20px;font-weight:600;
}
.header-right{margin-left:auto;display:flex;gap:8px}

.main{max-width:1280px;margin:0 auto;padding:24px 32px}

/* Tooltip */
.tip{position:relative;display:inline-flex}
.tip .tiptext{
  visibility:hidden;opacity:0;
  position:absolute;top:calc(100% + 8px);left:50%;transform:translateX(-50%);
  background:#1e293b;color:var(--text);border:1px solid var(--border);
  padding:8px 12px;border-radius:8px;font-size:12px;font-weight:400;
  white-space:nowrap;z-index:50;pointer-events:none;
  transition:opacity .15s,visibility .15s;
  box-shadow:0 4px 16px rgba(0,0,0,.4);
  line-height:1.4;max-width:320px;white-space:normal;text-align:left;
}
.tip .tiptext::after{
  content:"";position:absolute;bottom:100%;left:50%;transform:translateX(-50%);
  border:6px solid transparent;border-bottom-color:#1e293b;
}
.header-right .tip .tiptext{left:auto;right:0;transform:none}
.header-right .tip .tiptext::after{left:auto;right:16px;transform:none}
.tip:hover .tiptext{visibility:visible;opacity:1}

/* Controls */
.controls{
  background:var(--bg-card);border:1px solid var(--border);
  border-radius:var(--radius);padding:20px 24px;margin-bottom:20px;
  display:flex;flex-wrap:wrap;align-items:center;gap:12px;
}
.controls .label{font-size:13px;color:var(--text-dim);font-weight:600;text-transform:uppercase;letter-spacing:.5px}

.btn{
  display:inline-flex;align-items:center;gap:6px;
  padding:10px 20px;border:1px solid var(--border);border-radius:8px;
  background:var(--bg-code);color:var(--text);font-size:14px;font-weight:600;
  cursor:pointer;transition:all .15s;text-decoration:none;
}
.btn:hover:not(:disabled){border-color:var(--accent);color:var(--accent);background:rgba(0,200,255,.08)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn.primary{background:rgba(0,200,255,.15);border-color:var(--accent);color:var(--accent)}
.btn.danger{border-color:var(--red);color:var(--red)}
.btn.danger:hover:not(:disabled){background:rgba(248,113,113,.1)}
.btn.small{padding:6px 14px;font-size:12px}
.btn.green{border-color:var(--green);color:var(--green)}
.btn.green:hover:not(:disabled){background:rgba(52,211,153,.1)}

.template-selector{display:flex;gap:6px;align-items:center}
.tpl-btn{
  width:36px;height:36px;border-radius:6px;border:2px solid var(--border);
  cursor:pointer;font-size:12px;font-weight:700;color:var(--text);
  display:flex;align-items:center;justify-content:center;transition:all .15s;
}
.tpl-btn:hover,.tpl-btn.active{border-color:var(--accent)}
.tpl-btn.active{background:rgba(0,200,255,.15)}

.separator{width:1px;height:32px;background:var(--border);margin:0 4px}

/* Grid */
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}
@media(max-width:800px){.grid{grid-template-columns:1fr}}

/* Cards */
.card{
  background:var(--bg-card);border:1px solid var(--border);
  border-radius:var(--radius);padding:20px 24px;
}
.card h2{font-size:14px;text-transform:uppercase;letter-spacing:.5px;color:var(--text-dim);margin-bottom:14px;font-weight:600}
.card h3{font-size:20px;margin-bottom:8px;line-height:1.3}
.card .meta{font-size:13px;color:var(--text-dim);margin-bottom:12px}
.card .meta span{margin-right:16px}
.card .virality{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:700}
.card ul{list-style:none;padding:0}
.card ul li{
  font-size:14px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.04);
  color:var(--text-dim);
}
.card ul li::before{content:"\2192 ";color:var(--accent);font-weight:700}

.empty-state{color:var(--text-dim);font-size:14px;font-style:italic}

/* Slides grid */
.slides-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.slides-grid img{
  width:100%;border-radius:6px;border:1px solid var(--border);
  cursor:pointer;transition:transform .15s,border-color .15s;
  aspect-ratio:1080/1350;object-fit:cover;
}
.slides-grid img:hover{transform:scale(1.03);border-color:var(--accent)}
@media(max-width:600px){.slides-grid{grid-template-columns:repeat(2,1fr)}}

/* Output console */
.console{
  background:var(--bg-card);border:1px solid var(--border);
  border-radius:var(--radius);padding:20px 24px;margin-bottom:20px;
}
.console h2{font-size:14px;text-transform:uppercase;letter-spacing:.5px;color:var(--text-dim);margin-bottom:14px;font-weight:600;display:flex;align-items:center;gap:10px}
.console pre{
  background:var(--bg-code);border:1px solid var(--border);
  border-radius:8px;padding:16px 20px;
  font-family:"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
  font-size:12px;line-height:1.7;color:var(--text-dim);
  max-height:400px;overflow-y:auto;white-space:pre-wrap;word-break:break-word;
}

/* Status indicator */
.status-dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.status-dot.idle{background:var(--text-dim)}
.status-dot.running{background:var(--orange);animation:pulse 1s infinite}
.status-dot.done{background:var(--green)}
.status-dot.error{background:var(--red)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

/* Lightbox */
.lightbox{
  display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);
  z-index:1000;align-items:center;justify-content:center;
}
.lightbox.open{display:flex}
.lightbox img{max-height:90vh;max-width:70vw;border-radius:8px;box-shadow:0 8px 40px rgba(0,0,0,.5);user-select:none}
.lb-nav{
  position:absolute;top:50%;transform:translateY(-50%);
  background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);
  color:#fff;font-size:28px;width:48px;height:48px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  cursor:pointer;transition:background .15s;user-select:none;
}
.lb-nav:hover{background:rgba(255,255,255,.25)}
.lb-prev{left:20px}
.lb-next{right:20px}
.lb-counter{
  position:absolute;bottom:24px;left:50%;transform:translateX(-50%);
  color:rgba(255,255,255,.7);font-size:14px;font-weight:600;
}
.lb-close{
  position:absolute;top:16px;right:20px;
  background:none;border:none;color:rgba(255,255,255,.6);
  font-size:32px;cursor:pointer;line-height:1;
}
.lb-close:hover{color:#fff}

/* ── API Keys Panel ─────────────────────────────────────────────── */
.keys-panel{
  display:none;position:fixed;inset:0;z-index:900;
  background:rgba(0,0,0,.6);align-items:center;justify-content:center;
}
.keys-panel.open{display:flex}
.keys-modal{
  background:var(--bg-card);border:1px solid var(--border);border-radius:12px;
  width:700px;max-width:95vw;max-height:90vh;overflow-y:auto;
  box-shadow:0 12px 48px rgba(0,0,0,.5);
}
.keys-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:20px 24px;border-bottom:1px solid var(--border);
  position:sticky;top:0;background:var(--bg-card);z-index:1;
  border-radius:12px 12px 0 0;
}
.keys-header h2{font-size:18px;font-weight:700;margin:0}
.keys-close{
  background:none;border:none;color:var(--text-dim);font-size:24px;
  cursor:pointer;padding:4px 8px;line-height:1;
}
.keys-close:hover{color:var(--text)}
.keys-body{padding:20px 24px}
.keys-footer{
  padding:16px 24px;border-top:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;
  position:sticky;bottom:0;background:var(--bg-card);
  border-radius:0 0 12px 12px;
}

.key-group-title{
  font-size:11px;text-transform:uppercase;letter-spacing:1px;
  color:var(--accent);font-weight:700;margin:20px 0 10px;
  padding-bottom:6px;border-bottom:1px solid var(--border);
}
.key-group-title:first-child{margin-top:0}

.key-row{margin-bottom:16px}
.key-label{
  display:flex;align-items:center;gap:8px;
  font-size:13px;font-weight:600;margin-bottom:4px;
}
.key-label .dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.key-label .dot.on{background:var(--green)}
.key-label .dot.off{background:var(--red)}
.key-label .dot.opt{background:var(--text-dim)}
.key-label .req{font-size:10px;color:var(--red);font-weight:700}
.key-label a{
  font-size:11px;color:var(--accent);text-decoration:none;margin-left:auto;opacity:.7;
}
.key-label a:hover{opacity:1;text-decoration:underline}
.key-hint{font-size:12px;color:var(--text-dim);margin-bottom:6px;line-height:1.4}
.key-input{
  width:100%;padding:9px 12px;
  background:var(--bg-code);border:1px solid var(--border);border-radius:6px;
  color:var(--text);font-family:monospace;font-size:13px;
  transition:border-color .15s;
}
.key-input:focus{outline:none;border-color:var(--accent)}
.key-input::placeholder{color:#475569}

.save-msg{font-size:13px;color:var(--green);opacity:0;transition:opacity .3s}
.save-msg.show{opacity:1}

@keyframes spin{to{transform:rotate(360deg)}}

/* ── Prompts Panel ─────────────────────────────────────────────── */
.prompts-panel{
  display:none;position:fixed;inset:0;z-index:900;
  background:rgba(0,0,0,.6);align-items:center;justify-content:center;
}
.prompts-panel.open{display:flex}
.prompts-modal{
  background:var(--bg-card);border:1px solid var(--border);border-radius:12px;
  width:900px;max-width:95vw;max-height:90vh;overflow-y:auto;
  box-shadow:0 12px 48px rgba(0,0,0,.5);
}
.prompts-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:20px 24px;border-bottom:1px solid var(--border);
  position:sticky;top:0;background:var(--bg-card);z-index:1;
  border-radius:12px 12px 0 0;
}
.prompts-header h2{font-size:18px;font-weight:700;margin:0}

.prompts-tabs{
  display:flex;gap:0;border-bottom:1px solid var(--border);
  padding:0 24px;position:sticky;top:63px;background:var(--bg-card);z-index:1;
}
.prompts-tab{
  padding:12px 20px;font-size:13px;font-weight:600;
  color:var(--text-dim);cursor:pointer;border-bottom:2px solid transparent;
  transition:all .15s;background:none;border-top:none;border-left:none;border-right:none;
}
.prompts-tab:hover{color:var(--text)}
.prompts-tab.active{color:var(--accent);border-bottom-color:var(--accent)}

.prompts-body{padding:20px 24px}

.prompt-card{
  background:var(--bg-code);border:1px solid var(--border);border-radius:10px;
  padding:18px 20px;margin-bottom:16px;
}
.prompt-card-header{
  display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-wrap:wrap;
}
.prompt-card-header h3{font-size:15px;font-weight:700;margin:0}
.prompt-badge{
  font-size:10px;padding:2px 8px;border-radius:10px;font-weight:700;
  text-transform:uppercase;letter-spacing:.5px;
}
.prompt-badge.meta{background:rgba(192,132,252,.15);color:var(--accent2)}
.prompt-badge.fallback{background:rgba(251,146,60,.15);color:var(--orange)}
.prompt-badge.custom{background:rgba(52,211,153,.15);color:var(--green)}
.prompt-desc{font-size:12px;color:var(--text-dim);margin-bottom:10px;line-height:1.4}
.prompt-module{font-size:11px;color:var(--text-dim);opacity:.7}

.prompt-vars{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.prompt-var{
  font-size:11px;padding:3px 8px;border-radius:6px;
  background:rgba(0,200,255,.1);color:var(--accent);
  font-family:monospace;border:1px solid rgba(0,200,255,.2);
}

.prompt-textarea{
  width:100%;min-height:180px;padding:12px 14px;
  background:var(--bg);border:1px solid var(--border);border-radius:8px;
  color:var(--text);font-family:"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
  font-size:12px;line-height:1.6;resize:vertical;
  transition:border-color .15s;
}
.prompt-textarea:focus{outline:none;border-color:var(--accent)}
.prompt-textarea.error{border-color:var(--red)}

.prompt-actions{
  display:flex;align-items:center;gap:10px;margin-top:10px;
}
.prompt-msg{font-size:12px;margin-left:auto;opacity:0;transition:opacity .3s}
.prompt-msg.show{opacity:1}
.prompt-msg.ok{color:var(--green)}
.prompt-msg.err{color:var(--red)}

.prompt-note{
  font-size:11px;color:var(--text-dim);padding:12px 16px;
  background:rgba(0,200,255,.05);border:1px solid rgba(0,200,255,.1);
  border-radius:8px;margin-bottom:16px;line-height:1.5;
}

/* ── Sources Panel ─────────────────────────────────────────────── */
.sources-panel{
  display:none;position:fixed;inset:0;z-index:900;
  background:rgba(0,0,0,.6);align-items:center;justify-content:center;
}
.sources-panel.open{display:flex}
.sources-modal{
  background:var(--bg-card);border:1px solid var(--border);border-radius:12px;
  width:750px;max-width:95vw;max-height:90vh;overflow-y:auto;
  box-shadow:0 12px 48px rgba(0,0,0,.5);
}
.sources-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:20px 24px;border-bottom:1px solid var(--border);
  position:sticky;top:0;background:var(--bg-card);z-index:1;
  border-radius:12px 12px 0 0;
}
.sources-header h2{font-size:18px;font-weight:700;margin:0}
.sources-body{padding:20px 24px}
.sources-footer{
  padding:16px 24px;border-top:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;
  position:sticky;bottom:0;background:var(--bg-card);
  border-radius:0 0 12px 12px;
}

.src-section{margin-bottom:24px}
.src-section h3{
  font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;
  color:var(--accent);margin-bottom:4px;
}
.src-section .src-hint{font-size:12px;color:var(--text-dim);margin-bottom:10px;line-height:1.4}

.src-tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}
.src-tag{
  display:inline-flex;align-items:center;gap:5px;
  padding:5px 10px;border-radius:6px;font-size:12px;
  background:var(--bg-code);border:1px solid var(--border);
  color:var(--text);font-family:monospace;
}
.src-tag .x{
  cursor:pointer;color:var(--text-dim);font-size:14px;font-weight:700;
  line-height:1;margin-left:2px;
}
.src-tag .x:hover{color:var(--red)}

.src-add{display:flex;gap:6px}
.src-add input{
  flex:1;padding:7px 10px;
  background:var(--bg-code);border:1px solid var(--border);border-radius:6px;
  color:var(--text);font-family:monospace;font-size:12px;
}
.src-add input:focus{outline:none;border-color:var(--accent)}
.src-add input::placeholder{color:#475569}

.src-textarea{
  width:100%;padding:9px 12px;
  background:var(--bg-code);border:1px solid var(--border);border-radius:6px;
  color:var(--text);font-family:monospace;font-size:12px;
  transition:border-color .15s;
}
.src-textarea:focus{outline:none;border-color:var(--accent)}
.src-textarea::placeholder{color:#475569}

.sources-msg{font-size:13px;opacity:0;transition:opacity .3s}
.sources-msg.show{opacity:1}
.src-custom-badge{
  font-size:10px;padding:2px 8px;border-radius:10px;font-weight:700;
  background:rgba(52,211,153,.15);color:var(--green);margin-left:8px;
}
</style>
</head>
<body>

<div class="header">
  <h1><span>IG</span> AI Bot</h1>
  <span class="badge" style="background:rgba(0,200,255,.15);color:var(--accent)">Panel de Control</span>
  <span class="badge" id="statusBadge" style="background:rgba(52,211,153,.15);color:var(--green)">idle</span>

  <div class="header-right">
    <div class="tip">
      <button class="btn small" onclick="openSourcesPanel()">📡 Fuentes</button>
      <span class="tiptext">Configurar las fuentes de investigaci&oacute;n: subreddits, RSS, trends keywords, dominios NewsAPI</span>
    </div>
    <div class="tip">
      <button class="btn small" onclick="openPromptsPanel()">✏️ Prompts</button>
      <span class="tiptext">Ver y editar los prompts del sistema (investigaci&oacute;n, contenido, imagen)</span>
    </div>
    <div class="tip">
      <button class="btn small" onclick="openKeysPanel()">🔑 API Keys</button>
      <span class="tiptext">Configurar las claves de API necesarias para el bot</span>
    </div>
    <div class="tip">
      <a class="btn small" href="/docs" target="_blank" style="text-decoration:none">📖 Docs</a>
      <span class="tiptext">Abrir la documentaci&oacute;n completa en otra pesta&ntilde;a</span>
    </div>
  </div>
</div>

<div class="main">

  <!-- Controls -->
  <div class="controls">
    <span class="label">Ejecutar:</span>

    <div class="tip">
      <button class="btn" onclick="run('test')" id="btnTest">🧪 Test</button>
      <span class="tiptext">Usa datos de ejemplo (sin llamadas a APIs). Ideal para probar el dise&ntilde;o visual sin gastar cr&eacute;ditos.</span>
    </div>

    <div class="tip">
      <button class="btn" onclick="run('dry-run')" id="btnDry">🔍 Dry Run</button>
      <span class="tiptext">Ejecuta el pipeline completo con APIs reales, pero NO publica en Instagram. Perfecto para verificar el resultado.</span>
    </div>

    <div class="tip">
      <button class="btn danger" onclick="run('live')" id="btnLive">🚀 Live</button>
      <span class="tiptext">Pipeline completo + publicaci&oacute;n real en Instagram. Requiere todas las API keys configuradas.</span>
    </div>

    <div class="separator"></div>

    <div class="tip">
      <span class="label">Template:</span>
      <span class="tiptext">Esquema de color del carrusel. &laquo;A&raquo; rota autom&aacute;ticamente entre los 4 templates.</span>
    </div>
    <div class="template-selector">
      <div class="tip">
        <div class="tpl-btn active" data-tpl="auto" onclick="selectTemplate(this)">A</div>
        <span class="tiptext">Auto &mdash; Rota autom&aacute;ticamente</span>
      </div>
      <div class="tip">
        <div class="tpl-btn" data-tpl="0" onclick="selectTemplate(this)" style="background:linear-gradient(rgb(10,15,40),rgb(25,55,109))"></div>
        <span class="tiptext">dark_blue &mdash; Azul navy + cyan</span>
      </div>
      <div class="tip">
        <div class="tpl-btn" data-tpl="1" onclick="selectTemplate(this)" style="background:linear-gradient(rgb(20,5,35),rgb(75,20,120))"></div>
        <span class="tiptext">dark_purple &mdash; P&uacute;rpura + magenta</span>
      </div>
      <div class="tip">
        <div class="tpl-btn" data-tpl="2" onclick="selectTemplate(this)" style="background:linear-gradient(rgb(5,20,15),rgb(15,80,60))"></div>
        <span class="tiptext">dark_green &mdash; Verde oscuro + mint</span>
      </div>
      <div class="tip">
        <div class="tpl-btn" data-tpl="3" onclick="selectTemplate(this)" style="background:linear-gradient(rgb(15,15,25),rgb(40,40,70))"></div>
        <span class="tiptext">midnight &mdash; Carb&oacute;n + naranja</span>
      </div>
    </div>
  </div>

  <!-- Topic + Slides -->
  <div class="grid">
    <div class="card" id="topicCard">
      <div class="tip" style="display:inline-flex">
        <h2>Último Topic</h2>
        <span class="tiptext">El tema seleccionado en la &uacute;ltima ejecuci&oacute;n del pipeline. Se guarda en data/last_topic.json.</span>
      </div>
      <div id="topicContent" class="empty-state">Cargando...</div>
    </div>
    <div class="card">
      <div class="tip" style="display:inline-flex">
        <h2>Preview Slides</h2>
        <span class="tiptext">Im&aacute;genes del carrusel generadas (1080&times;1350px). Click en cualquiera para ampliar.</span>
      </div>
      <div id="slidesContent" class="empty-state">Cargando...</div>
    </div>
  </div>

  <!-- Console -->
  <div class="console">
    <h2>
      <span class="status-dot idle" id="statusDot"></span>
      <div class="tip" style="display:inline-flex">
        Pipeline Output
        <span class="tiptext">Salida en tiempo real del pipeline. Muestra cada paso: Research &rarr; Content &rarr; Design &rarr; Engagement &rarr; Publish.</span>
      </div>
      <span id="elapsed" style="font-size:12px;color:var(--text-dim);font-weight:400"></span>
    </h2>
    <pre id="output">Listo. Selecciona un modo y haz click para ejecutar el pipeline.</pre>
  </div>

</div>

<!-- Lightbox -->
<div class="lightbox" id="lightbox" onclick="if(event.target===this)closeLightbox()">
  <button class="lb-close" onclick="closeLightbox()">&times;</button>
  <div class="lb-nav lb-prev" onclick="lbNav(-1)">&#8249;</div>
  <img id="lightboxImg" src="" alt="Slide preview">
  <div class="lb-nav lb-next" onclick="lbNav(1)">&#8250;</div>
  <div class="lb-counter" id="lbCounter"></div>
</div>

<!-- API Keys Panel -->
<div class="keys-panel" id="keysPanel" onclick="if(event.target===this)closeKeysPanel()">
  <div class="keys-modal">
    <div class="keys-header">
      <h2>🔑 API Keys</h2>
      <button class="keys-close" onclick="closeKeysPanel()">&times;</button>
    </div>
    <div class="keys-body" id="keysBody">
      <p class="empty-state">Cargando...</p>
    </div>
    <div class="keys-footer">
      <span class="save-msg" id="saveMsg">Guardado correctamente</span>
      <button class="btn green" onclick="saveKeys()">💾 Guardar en .env</button>
    </div>
  </div>
</div>

<!-- Sources Panel -->
<div class="sources-panel" id="sourcesPanel" onclick="if(event.target===this)closeSourcesPanel()">
  <div class="sources-modal">
    <div class="sources-header">
      <h2>📡 Fuentes de Investigacion<span class="src-custom-badge" id="srcCustomBadge" style="display:none">Personalizado</span></h2>
      <button class="keys-close" onclick="closeSourcesPanel()">&times;</button>
    </div>
    <div class="sources-body" id="sourcesBody">
      <p class="empty-state">Cargando...</p>
    </div>
    <div class="sources-footer">
      <span class="sources-msg" id="sourcesMsg"></span>
      <div style="display:flex;gap:8px">
        <button class="btn small" id="srcResetBtn" onclick="resetSources()">↩️ Restaurar Originales</button>
        <button class="btn small green" onclick="saveSources()">💾 Guardar</button>
      </div>
    </div>
  </div>
</div>

<!-- Prompts Panel -->
<div class="prompts-panel" id="promptsPanel" onclick="if(event.target===this)closePromptsPanel()">
  <div class="prompts-modal">
    <div class="prompts-header">
      <h2>✏️ Editor de Prompts</h2>
      <button class="keys-close" onclick="closePromptsPanel()">&times;</button>
    </div>
    <div class="prompts-tabs" id="promptsTabs"></div>
    <div class="prompts-body" id="promptsBody">
      <p class="empty-state">Cargando...</p>
    </div>
  </div>
</div>

<script>
let selectedTemplate = null;
let polling = null;

/* ── Template selector ────────────────────────────────── */
function selectTemplate(el) {
  document.querySelectorAll('.tpl-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  const val = el.dataset.tpl;
  selectedTemplate = val === 'auto' ? null : parseInt(val);
}

/* ── Pipeline execution ───────────────────────────────── */
function setButtons(disabled) {
  ['btnTest','btnDry','btnLive'].forEach(id => {
    document.getElementById(id).disabled = disabled;
  });
}

async function run(mode) {
  if (mode === 'live' && !confirm('¿Ejecutar en modo LIVE?\nEsto publicará en Instagram.')) return;

  setButtons(true);
  document.getElementById('output').textContent = `Iniciando pipeline (${mode})...\n`;
  updateStatusUI('running');

  const body = { mode };
  if (selectedTemplate !== null) body.template = selectedTemplate;

  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json();
      document.getElementById('output').textContent = `Error: ${err.error}`;
      setButtons(false);
      updateStatusUI('error');
      return;
    }
  } catch(e) {
    document.getElementById('output').textContent = `Error de conexión: ${e}`;
    setButtons(false);
    updateStatusUI('error');
    return;
  }

  if (polling) clearInterval(polling);
  polling = setInterval(pollStatus, 1500);
}

async function pollStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    document.getElementById('output').textContent = data.output || 'Esperando output...';
    document.getElementById('elapsed').textContent = data.elapsed ? `${data.elapsed}s` : '';
    const pre = document.getElementById('output');
    pre.scrollTop = pre.scrollHeight;
    updateStatusUI(data.status);
    if (data.status === 'done' || data.status === 'error') {
      clearInterval(polling);
      polling = null;
      setButtons(false);
      setTimeout(loadState, 500);
    }
  } catch(e) {}
}

function updateStatusUI(status) {
  document.getElementById('statusDot').className = `status-dot ${status}`;
  const badge = document.getElementById('statusBadge');
  const labels = {idle:'idle', running:'ejecutando...', done:'completado', error:'error'};
  const colors = {
    idle:    'background:rgba(148,163,184,.15);color:var(--text-dim)',
    running: 'background:rgba(251,146,60,.15);color:var(--orange)',
    done:    'background:rgba(52,211,153,.15);color:var(--green)',
    error:   'background:rgba(248,113,113,.15);color:var(--red)',
  };
  badge.textContent = labels[status] || status;
  badge.style.cssText = colors[status] || colors.idle;
}

/* ── State loading ────────────────────────────────────── */
async function loadState() {
  try {
    const res = await fetch('/api/state');
    const data = await res.json();

    // Topic
    const topicEl = document.getElementById('topicContent');
    if (data.topic) {
      const t = data.topic;
      const v = t.virality_score || '?';
      const vColor = v >= 8 ? 'var(--green)' : v >= 6 ? 'var(--orange)' : 'var(--text-dim)';
      const points = (t.key_points || []).map(p => `<li>${esc(p)}</li>`).join('');
      topicEl.innerHTML = `
        <h3>${esc(t.topic||'Sin título')}</h3>
        <div class="meta">
          <span class="virality" style="background:${vColor}22;color:${vColor}">Virality: ${v}/10</span>
          <span>${esc(t.topic_en||'')}</span>
        </div>
        <p style="font-size:14px;color:var(--text-dim);margin-bottom:10px">${esc(t.why||'')}</p>
        <ul>${points}</ul>
      `;
    } else {
      topicEl.innerHTML = '<span class="empty-state">Sin topic. Ejecuta el pipeline para generar uno.</span>';
    }

    // Slides
    const slidesEl = document.getElementById('slidesContent');
    if (data.slides && data.slides.length > 0) {
      const imgs = data.slides.map(s =>
        `<img src="/slides/${s}?t=${Date.now()}" alt="${s}" onclick="openLightbox(this.src)" loading="lazy">`
      ).join('');
      slidesEl.innerHTML = `<div class="slides-grid">${imgs}</div>`;
    } else {
      slidesEl.innerHTML = '<span class="empty-state">Sin slides. Ejecuta el pipeline para generarlos.</span>';
    }
  } catch(e) {
    console.error('Failed to load state:', e);
  }
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

let lbSlides = [];
let lbIndex = 0;

function openLightbox(src) {
  // Collect all slide srcs from the grid
  lbSlides = [...document.querySelectorAll('.slides-grid img')].map(img => img.src);
  lbIndex = lbSlides.indexOf(src);
  if (lbIndex < 0) lbIndex = 0;
  lbShow();
  document.getElementById('lightbox').classList.add('open');
}

function closeLightbox() {
  document.getElementById('lightbox').classList.remove('open');
}

function lbShow() {
  document.getElementById('lightboxImg').src = lbSlides[lbIndex];
  document.getElementById('lbCounter').textContent = `${lbIndex + 1} / ${lbSlides.length}`;
}

function lbNav(dir) {
  lbIndex = (lbIndex + dir + lbSlides.length) % lbSlides.length;
  lbShow();
}

document.addEventListener('keydown', e => {
  const lb = document.getElementById('lightbox');
  if (!lb.classList.contains('open')) return;
  if (e.key === 'ArrowLeft')  { e.preventDefault(); lbNav(-1); }
  if (e.key === 'ArrowRight') { e.preventDefault(); lbNav(1); }
  if (e.key === 'Escape')     { e.preventDefault(); closeLightbox(); }
});

/* ── API Keys Panel ───────────────────────────────────── */
function openKeysPanel() {
  document.getElementById('keysPanel').classList.add('open');
  loadKeys();
}
function closeKeysPanel() {
  document.getElementById('keysPanel').classList.remove('open');
}

async function loadKeys() {
  const body = document.getElementById('keysBody');
  try {
    const res = await fetch('/api/keys');
    const keys = await res.json();

    let html = '';
    let currentGroup = '';

    keys.forEach(k => {
      if (k.group !== currentGroup) {
        currentGroup = k.group;
        html += `<div class="key-group-title">${esc(currentGroup)}</div>`;
      }

      const dotClass = k.configured ? 'on' : (k.required ? 'off' : 'opt');
      const reqBadge = k.required ? '<span class="req">REQUERIDA</span>' : '';
      const link = k.url ? `<a href="${k.url}" target="_blank">Obtener &rarr;</a>` : '';
      const inputType = k.secret ? 'password' : 'text';

      html += `
        <div class="key-row">
          <div class="key-label">
            <span class="dot ${dotClass}"></span>
            ${esc(k.label)}
            ${reqBadge}
            ${link}
          </div>
          <div class="key-hint">${esc(k.hint)}</div>
          <input class="key-input" type="${inputType}"
                 data-key="${k.key}" data-secret="${k.secret}"
                 value="${k.secret ? '' : esc(k.value)}"
                 placeholder="${k.configured && k.secret ? k.value : esc(k.placeholder)}"
                 onfocus="if(this.dataset.secret==='true')this.type='text'"
                 onblur="if(this.dataset.secret==='true')this.type='password'"
          >
        </div>
      `;
    });

    body.innerHTML = html;
  } catch(e) {
    body.innerHTML = '<p class="empty-state">Error cargando API keys.</p>';
  }
}

async function saveKeys() {
  const inputs = document.querySelectorAll('.key-input');
  const data = {};
  inputs.forEach(inp => {
    const val = inp.value.trim();
    if (val && !val.startsWith('***')) {
      data[inp.dataset.key] = val;
    }
  });

  if (Object.keys(data).length === 0) {
    const msg = document.getElementById('saveMsg');
    msg.textContent = 'No hay cambios para guardar';
    msg.style.color = 'var(--orange)';
    msg.classList.add('show');
    setTimeout(() => msg.classList.remove('show'), 2000);
    return;
  }

  try {
    const res = await fetch('/api/keys', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data),
    });
    const result = await res.json();
    const msg = document.getElementById('saveMsg');
    msg.textContent = `Guardado: ${result.saved} clave(s) actualizadas`;
    msg.style.color = 'var(--green)';
    msg.classList.add('show');
    setTimeout(() => { msg.classList.remove('show'); loadKeys(); }, 2000);
  } catch(e) {
    const msg = document.getElementById('saveMsg');
    msg.textContent = 'Error al guardar';
    msg.style.color = 'var(--red)';
    msg.classList.add('show');
    setTimeout(() => msg.classList.remove('show'), 2000);
  }
}

/* ── Prompts Panel ────────────────────────────────────── */
let promptsData = [];
let activePromptTab = null;

function openPromptsPanel() {
  document.getElementById('promptsPanel').classList.add('open');
  loadPrompts();
}
function closePromptsPanel() {
  document.getElementById('promptsPanel').classList.remove('open');
}

async function loadPrompts() {
  const body = document.getElementById('promptsBody');
  const tabs = document.getElementById('promptsTabs');
  try {
    const res = await fetch('/api/prompts');
    promptsData = await res.json();

    // Build tabs from unique categories
    const categories = [...new Set(promptsData.map(p => p.category))];
    if (!activePromptTab) activePromptTab = categories[0];

    tabs.innerHTML = categories.map(cat =>
      `<button class="prompts-tab ${cat === activePromptTab ? 'active' : ''}"
              onclick="switchPromptTab('${cat}')">${esc(cat)}</button>`
    ).join('');

    renderPromptCards();
  } catch(e) {
    body.innerHTML = '<p class="empty-state">Error cargando prompts.</p>';
  }
}

function switchPromptTab(cat) {
  activePromptTab = cat;
  document.querySelectorAll('.prompts-tab').forEach(t => {
    t.classList.toggle('active', t.textContent === cat);
  });
  renderPromptCards();
}

function renderPromptCards() {
  const body = document.getElementById('promptsBody');
  const filtered = promptsData.filter(p => p.category === activePromptTab);

  let html = `<div class="prompt-note">
    Las llaves dobles <code>{{ }}</code> son literales y aparecen tal cual en el texto final.
    Las llaves simples <code>{variable}</code> se reemplazan autom&aacute;ticamente con datos reales durante la ejecuci&oacute;n.
  </div>`;

  filtered.forEach(p => {
    const typeBadge = `<span class="prompt-badge ${p.type}">${p.type}</span>`;
    const customBadge = p.custom ? '<span class="prompt-badge custom">Personalizado</span>' : '';
    const vars = p.variables.map(v =>
      `<span class="prompt-var">{${esc(v)}}</span>`
    ).join('');

    html += `
      <div class="prompt-card" data-prompt-id="${p.id}">
        <div class="prompt-card-header">
          <h3>${esc(p.name)}</h3>
          ${typeBadge} ${customBadge}
          <span class="prompt-module">${esc(p.module)}</span>
        </div>
        <div class="prompt-desc">${esc(p.description)}</div>
        ${vars ? `<div class="prompt-vars">${vars}</div>` : ''}
        <textarea class="prompt-textarea" id="prompt-text-${p.id}"
                  spellcheck="false">${esc(p.text)}</textarea>
        <div class="prompt-actions">
          <button class="btn small green" onclick="savePrompt('${p.id}')">💾 Guardar</button>
          <button class="btn small" onclick="resetPrompt('${p.id}')"
                  ${!p.custom ? 'disabled title="Ya es el original"' : ''}>↩️ Restaurar Original</button>
          <span class="prompt-msg" id="prompt-msg-${p.id}"></span>
        </div>
      </div>
    `;
  });

  body.innerHTML = html;
}

function showPromptMsg(pid, text, type) {
  const el = document.getElementById(`prompt-msg-${pid}`);
  el.textContent = text;
  el.className = `prompt-msg show ${type}`;
  setTimeout(() => el.classList.remove('show'), 3000);
}

async function savePrompt(pid) {
  const textarea = document.getElementById(`prompt-text-${pid}`);
  const text = textarea.value;

  textarea.classList.remove('error');

  try {
    const res = await fetch('/api/prompts', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ id: pid, text }),
    });
    const result = await res.json();
    if (!res.ok) {
      textarea.classList.add('error');
      showPromptMsg(pid, result.error, 'err');
      return;
    }
    showPromptMsg(pid, 'Guardado correctamente', 'ok');
    // Refresh to update custom badge and restore button state
    setTimeout(loadPrompts, 1000);
  } catch(e) {
    showPromptMsg(pid, 'Error al guardar', 'err');
  }
}

async function resetPrompt(pid) {
  if (!confirm('¿Restaurar este prompt al texto original?\nSe perderán los cambios personalizados.')) return;

  try {
    const res = await fetch('/api/prompts/reset', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ id: pid }),
    });
    const result = await res.json();
    if (!res.ok) {
      showPromptMsg(pid, result.error, 'err');
      return;
    }
    showPromptMsg(pid, 'Restaurado al original', 'ok');
    setTimeout(loadPrompts, 500);
  } catch(e) {
    showPromptMsg(pid, 'Error al restaurar', 'err');
  }
}

/* ── Sources Panel ────────────────────────────────────── */
let srcConfig = {};
let srcDefaults = {};
let srcIsCustom = false;

function openSourcesPanel() {
  document.getElementById('sourcesPanel').classList.add('open');
  loadSources();
}
function closeSourcesPanel() {
  document.getElementById('sourcesPanel').classList.remove('open');
}

async function loadSources() {
  const body = document.getElementById('sourcesBody');
  try {
    const res = await fetch('/api/research-config');
    const data = await res.json();
    srcConfig = data.config;
    srcDefaults = data.defaults;
    srcIsCustom = data.custom;
    renderSources();
  } catch(e) {
    body.innerHTML = '<p class="empty-state">Error cargando config.</p>';
  }
}

function renderSources() {
  const badge = document.getElementById('srcCustomBadge');
  badge.style.display = srcIsCustom ? 'inline' : 'none';
  document.getElementById('srcResetBtn').disabled = !srcIsCustom;

  const body = document.getElementById('sourcesBody');
  body.innerHTML = `
    <div class="src-section">
      <h3>Subreddits</h3>
      <div class="src-hint">Subreddits de Reddit de los que se extraen posts trending. Ejemplo: artificial, technology</div>
      <div class="src-tags" id="srcSubreddits">
        ${srcConfig.subreddits.map(s => `<span class="src-tag">${esc(s)}<span class="x" onclick="srcRemove('subreddits','${esc(s)}')">&times;</span></span>`).join('')}
      </div>
      <div class="src-add">
        <input id="srcAddSubreddit" placeholder="Nuevo subreddit (ej: LocalLLaMA)" onkeydown="if(event.key==='Enter')srcAdd('subreddits','srcAddSubreddit')">
        <button class="btn small" onclick="srcAdd('subreddits','srcAddSubreddit')">+</button>
      </div>
    </div>

    <div class="src-section">
      <h3>RSS Feeds</h3>
      <div class="src-hint">URLs de feeds RSS/Atom. Se extraen los 10 art&iacute;culos m&aacute;s recientes de cada uno.</div>
      <div class="src-tags" id="srcRssFeeds">
        ${srcConfig.rss_feeds.map(s => `<span class="src-tag">${esc(s)}<span class="x" onclick="srcRemoveByVal('rss_feeds',\`${esc(s)}\`)">&times;</span></span>`).join('')}
      </div>
      <div class="src-add">
        <input id="srcAddRss" placeholder="URL del feed (ej: https://example.com/feed/)" onkeydown="if(event.key==='Enter')srcAdd('rss_feeds','srcAddRss')">
        <button class="btn small" onclick="srcAdd('rss_feeds','srcAddRss')">+</button>
      </div>
    </div>

    <div class="src-section">
      <h3>Google Trends Keywords</h3>
      <div class="src-hint">Palabras clave para filtrar Google Trends. Solo se muestran tendencias que contengan alguna de estas palabras.</div>
      <div class="src-tags" id="srcTrendsKw">
        ${srcConfig.trends_keywords.map(s => `<span class="src-tag">${esc(s)}<span class="x" onclick="srcRemove('trends_keywords','${esc(s)}')">&times;</span></span>`).join('')}
      </div>
      <div class="src-add">
        <input id="srcAddTrend" placeholder="Nueva keyword (ej: blockchain)" onkeydown="if(event.key==='Enter')srcAdd('trends_keywords','srcAddTrend')">
        <button class="btn small" onclick="srcAdd('trends_keywords','srcAddTrend')">+</button>
      </div>
    </div>

    <div class="src-section">
      <h3>NewsAPI Dominios</h3>
      <div class="src-hint">Dominios separados por coma. Se buscan art&iacute;culos recientes de estos sitios. Dejar vac&iacute;o para usar top-headlines gen&eacute;ricos.</div>
      <input class="src-textarea" id="srcNewsapiDomains" value="${esc(srcConfig.newsapi_domains)}"
             placeholder="techcrunch.com,theverge.com,arstechnica.com">
    </div>
  `;
}

function srcRemove(key, val) {
  srcConfig[key] = srcConfig[key].filter(v => v !== val);
  renderSources();
}

function srcRemoveByVal(key, val) {
  srcConfig[key] = srcConfig[key].filter(v => v !== val);
  renderSources();
}

function srcAdd(key, inputId) {
  const inp = document.getElementById(inputId);
  const val = inp.value.trim();
  if (!val) return;
  if (!srcConfig[key].includes(val)) {
    srcConfig[key].push(val);
  }
  inp.value = '';
  renderSources();
}

function showSourcesMsg(text, color) {
  const el = document.getElementById('sourcesMsg');
  el.textContent = text;
  el.style.color = color;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 3000);
}

async function saveSources() {
  // Read newsapi_domains from input
  const domainsInput = document.getElementById('srcNewsapiDomains');
  if (domainsInput) srcConfig.newsapi_domains = domainsInput.value.trim();

  try {
    const res = await fetch('/api/research-config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ config: srcConfig }),
    });
    const result = await res.json();
    if (!res.ok) {
      showSourcesMsg(result.error, 'var(--red)');
      return;
    }
    showSourcesMsg('Guardado correctamente', 'var(--green)');
    srcIsCustom = true;
    document.getElementById('srcCustomBadge').style.display = 'inline';
    document.getElementById('srcResetBtn').disabled = false;
  } catch(e) {
    showSourcesMsg('Error al guardar', 'var(--red)');
  }
}

async function resetSources() {
  if (!confirm('Restaurar todas las fuentes a los valores originales?')) return;
  try {
    const res = await fetch('/api/research-config/reset', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
    });
    if (res.ok) {
      showSourcesMsg('Restaurado a originales', 'var(--green)');
      srcIsCustom = false;
      loadSources();
    }
  } catch(e) {
    showSourcesMsg('Error al restaurar', 'var(--red)');
  }
}

/* ── Init ─────────────────────────────────────────────── */
loadState();
fetch('/api/status').then(r=>r.json()).then(d=>{
  if(d.status==='running'){
    setButtons(true);
    updateStatusUI('running');
    polling = setInterval(pollStatus, 1500);
  }
});
</script>

</body>
</html>"""


@app.route("/")
def dashboard():
    return DASHBOARD_HTML


@app.route("/docs")
def docs():
    docs_file = PROJECT_ROOT / "docs" / "index.html"
    if docs_file.exists():
        return docs_file.read_text()
    return "Docs not found", 404


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="IG AI Bot — Dashboard Web")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    args = parser.parse_args()

    print(f"\n  IG AI Bot — Panel de Control")
    print(f"  http://{args.host}:{args.port}\n")

    app.run(host=args.host, port=args.port, debug=False)
