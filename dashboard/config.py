from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent

OUTPUT_DIR = PROJECT_ROOT / "output"
DATA_DIR = PROJECT_ROOT / "data"
PROMPTS_DIR = DATA_DIR / "prompts"
RESEARCH_CONFIG_FILE = DATA_DIR / "research_config.json"
ENV_FILE = PROJECT_ROOT / ".env"
DOCS_FILE = PROJECT_ROOT / "docs" / "index.html"

FRONTEND_DIR = PROJECT_ROOT / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
FRONTEND_INDEX_FILE = FRONTEND_DIST_DIR / "index.html"

DASHBOARD_DATA_DIR = PACKAGE_ROOT / "data"
PROMPTS_CONFIG_FILE = DASHBOARD_DATA_DIR / "prompts_config.json"
API_KEYS_CONFIG_FILE = DASHBOARD_DATA_DIR / "api_keys_config.json"
RESEARCH_DEFAULTS_FILE = DASHBOARD_DATA_DIR / "research_defaults.json"


def _load_json_file(path: Path, fallback: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


PROMPTS_CONFIG = _load_json_file(PROMPTS_CONFIG_FILE, [])
API_KEYS_CONFIG = _load_json_file(API_KEYS_CONFIG_FILE, [])
DEFAULT_RESEARCH_CONFIG = _load_json_file(RESEARCH_DEFAULTS_FILE, {})


def ensure_dirs() -> None:
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
