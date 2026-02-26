from __future__ import annotations

import os

from dashboard.config import ENV_FILE


def read_env() -> dict:
    """Read .env file and return key-value dict, falling back to os.environ.

    In Cloud Run there is no .env file — secrets are set as environment
    variables directly, so we merge both sources (file takes precedence).
    """
    env = {}
    # First, pick up any real environment variables
    env.update(os.environ)
    # Then overlay with .env file values (if present)
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def write_env(updates: dict):
    """Update .env file, preserving comments and order. Adds new keys at the end."""
    lines = []
    existing_keys = set()

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
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

    for k, v in updates.items():
        if k not in existing_keys and v:
            lines.append(f"{k}={v}")

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def mask_value(value: str, is_secret: bool = True) -> str:
    """Mask a secret value, showing only the last 4 chars."""
    if not is_secret or not value:
        return value
    if len(value) <= 6:
        return "***"
    return "***" + value[-4:]
