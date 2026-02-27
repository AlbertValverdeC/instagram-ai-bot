#!/usr/bin/env python3
"""
Local encrypted secrets vault for instagram-ai-bot.

Features:
  - Encrypt/decrypt secrets with a user master password (AES-GCM + scrypt).
  - Migrate API keys/tokens from .env into an encrypted local vault file.
  - Execute any command with vaulted secrets injected as environment variables.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency 'cryptography'. Use project's virtualenv:\n"
        "  .venv/bin/python scripts/secrets_vault.py ..."
    ) from exc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_API_KEYS_CONFIG = PROJECT_ROOT / "dashboard" / "data" / "api_keys_config.json"
DEFAULT_VAULT_FILE = Path.home() / ".config" / "instagram-ai-bot" / "secrets.vault.json"
AAD = b"instagram-ai-bot-secrets-v1"
LINE_KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")
SENSITIVE_KEY_RE = re.compile(r"(TOKEN|API_KEY|SECRET|PASSWORD|DATABASE_URL)", re.IGNORECASE)

SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_LENGTH = 32

# Explicitly include publishing IDs with the auth material.
EXTRA_SENSITIVE_KEYS = {
    "INSTAGRAM_ACCOUNT_ID",
    "FACEBOOK_PAGE_ID",
    "META_ACCESS_TOKEN",
    "DASHBOARD_API_TOKEN",
    "DATABASE_URL",
}


def _decode_env_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def read_env_file(env_file: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_file.exists():
        return values
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = _decode_env_value(raw_value)
    return values


def read_api_keys_config(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def derive_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(
        salt=salt,
        length=SCRYPT_LENGTH,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_payload(payload: dict[str, str], password: str) -> dict:
    plaintext = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = derive_key(password, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, AAD)
    return {
        "version": 1,
        "kdf": {
            "name": "scrypt",
            "n": SCRYPT_N,
            "r": SCRYPT_R,
            "p": SCRYPT_P,
            "length": SCRYPT_LENGTH,
        },
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def decrypt_payload(blob: dict, password: str) -> dict[str, str]:
    try:
        salt = base64.b64decode(blob["salt_b64"])
        nonce = base64.b64decode(blob["nonce_b64"])
        ciphertext = base64.b64decode(blob["ciphertext_b64"])
    except Exception as exc:
        raise ValueError("Invalid vault file format.") from exc

    key = derive_key(password, salt)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, AAD)
    except Exception as exc:
        raise ValueError("Master password is incorrect or vault is corrupted.") from exc
    payload = json.loads(plaintext.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Invalid decrypted payload format.")
    return {str(k): str(v) for k, v in payload.items()}


def write_vault(vault_file: Path, blob: dict) -> None:
    vault_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = vault_file.with_suffix(vault_file.suffix + ".tmp")
    with os.fdopen(os.open(temp_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as fh:
        json.dump(blob, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(temp_file, vault_file)
    os.chmod(vault_file, 0o600)


def read_vault(vault_file: Path) -> dict:
    if not vault_file.exists():
        raise FileNotFoundError(f"Vault file not found: {vault_file}")
    return json.loads(vault_file.read_text(encoding="utf-8"))


def prompt_master_password(confirm: bool) -> str:
    password = getpass.getpass("Master password: ")
    if not password:
        raise SystemExit("Master password cannot be empty.")
    if confirm:
        confirmation = getpass.getpass("Confirm master password: ")
        if password != confirmation:
            raise SystemExit("Passwords do not match.")
    return password


def read_password_from_stdin(confirm: bool) -> str:
    prompt = "Master password (stdin): " if os.isatty(sys.stdin.fileno()) else ""
    if prompt:
        print(prompt, end="", flush=True)
    line = sys.stdin.readline()
    password = line.rstrip("\r\n")
    if not password:
        raise SystemExit("Master password is empty.")
    if confirm:
        if prompt:
            print("Confirm master password (stdin): ", end="", flush=True)
        line2 = sys.stdin.readline()
        confirmation = line2.rstrip("\r\n")
        if password != confirmation:
            raise SystemExit("Passwords do not match.")
    return password


def resolve_master_password(args: argparse.Namespace, *, confirm: bool) -> str:
    env_password = os.getenv("SECRETS_VAULT_MASTER_PASSWORD", "")
    if getattr(args, "password_stdin", False):
        return read_password_from_stdin(confirm=confirm)
    if env_password:
        return env_password
    return prompt_master_password(confirm=confirm)


def sensitive_key_set(api_keys_config: list[dict], env_values: dict[str, str]) -> set[str]:
    keys = set(EXTRA_SENSITIVE_KEYS)
    for cfg in api_keys_config:
        key = str(cfg.get("key", "")).strip()
        if not key:
            continue
        is_secret = bool(cfg.get("secret", True))
        if is_secret:
            keys.add(key)
    for key in env_values:
        if SENSITIVE_KEY_RE.search(key):
            keys.add(key)
    return keys


def redact_env_file(env_file: Path, keys_to_redact: set[str]) -> Path:
    if not env_file.exists():
        return env_file
    backup = env_file.with_name(f"{env_file.name}.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(env_file, backup)
    lines_out: list[str] = []
    for line in env_file.read_text(encoding="utf-8").splitlines():
        match = LINE_KEY_RE.match(line)
        if match and match.group(1) in keys_to_redact:
            key = match.group(1)
            lines_out.append(f"{key}=")
        else:
            lines_out.append(line)
    env_file.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    return backup


def cmd_migrate(args: argparse.Namespace) -> int:
    env_file = Path(args.env_file).expanduser().resolve()
    vault_file = Path(args.vault_file).expanduser().resolve()
    config_file = Path(args.api_keys_config).expanduser().resolve()

    env_values = read_env_file(env_file)
    if not env_values:
        raise SystemExit(f"No env values found in {env_file}")

    api_keys_cfg = read_api_keys_config(config_file)
    candidate_keys = sensitive_key_set(api_keys_cfg, env_values)
    selected = {
        key: value
        for key, value in env_values.items()
        if key in candidate_keys and str(value).strip() != ""
    }

    if not selected:
        print("No sensitive keys detected to migrate.")
        return 0

    vault_exists = vault_file.exists()
    password = resolve_master_password(args, confirm=not vault_exists)

    merged = {}
    if vault_exists:
        merged.update(decrypt_payload(read_vault(vault_file), password))
    merged.update(selected)

    write_vault(vault_file, encrypt_payload(merged, password))

    backup_file = None
    if args.redact_env:
        backup_file = redact_env_file(env_file, set(selected.keys()))

    print(f"Vault updated: {vault_file}")
    print(f"Migrated keys: {len(selected)}")
    print("Key names:")
    for key in sorted(selected.keys()):
        print(f"  - {key}")
    if backup_file:
        print(f".env backup: {backup_file}")
    return 0


def load_secrets_with_prompt(vault_file: Path, args: argparse.Namespace, *, confirm: bool = False) -> dict[str, str]:
    blob = read_vault(vault_file)
    password = resolve_master_password(args, confirm=confirm)
    return decrypt_payload(blob, password)


def cmd_list(args: argparse.Namespace) -> int:
    vault_file = Path(args.vault_file).expanduser().resolve()
    secrets_map = load_secrets_with_prompt(vault_file, args)
    print(f"Vault: {vault_file}")
    print(f"Stored keys: {len(secrets_map)}")
    for key in sorted(secrets_map.keys()):
        print(f"  - {key}")
    return 0


def cmd_exec(args: argparse.Namespace) -> int:
    vault_file = Path(args.vault_file).expanduser().resolve()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("Provide a command after '--'. Example: exec -- python dashboard.py")

    secrets_map = load_secrets_with_prompt(vault_file, args)
    env = os.environ.copy()
    env.update(secrets_map)
    try:
        proc = subprocess.run(command, env=env)
    except FileNotFoundError as exc:
        raise SystemExit(f"Command not found: {command[0]}") from exc
    return int(proc.returncode)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Encrypted local secrets vault manager.")
    parser.set_defaults(func=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--vault-file",
        default=str(DEFAULT_VAULT_FILE),
        help=f"Vault path (default: {DEFAULT_VAULT_FILE})",
    )
    common.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read master password from stdin (single line).",
    )

    p_migrate = subparsers.add_parser(
        "migrate",
        help="Migrate sensitive env vars from .env into encrypted vault.",
        parents=[common],
    )
    p_migrate.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help=f".env path (default: {DEFAULT_ENV_FILE})")
    p_migrate.add_argument(
        "--api-keys-config",
        default=str(DEFAULT_API_KEYS_CONFIG),
        help=f"API keys config path (default: {DEFAULT_API_KEYS_CONFIG})",
    )
    p_migrate.add_argument(
        "--redact-env",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Redact migrated keys from .env (default: true).",
    )
    p_migrate.set_defaults(func=cmd_migrate)

    p_list = subparsers.add_parser(
        "list",
        help="List stored secret key names (without values).",
        parents=[common],
    )
    p_list.set_defaults(func=cmd_list)

    p_exec = subparsers.add_parser(
        "exec",
        help="Run command with vaulted secrets injected as env vars.",
        parents=[common],
    )
    p_exec.add_argument("command", nargs=argparse.REMAINDER, help="Command to run.")
    p_exec.set_defaults(func=cmd_exec)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.func:
        parser.print_help()
        return 1
    try:
        return int(args.func(args))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
