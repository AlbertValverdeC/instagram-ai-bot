from __future__ import annotations

import os

from flask import jsonify, request

_DASHBOARD_API_TOKEN = os.getenv("DASHBOARD_API_TOKEN", "").strip()


def require_api_token():
    """
    Protect mutating endpoints in cloud deployments.

    If DASHBOARD_API_TOKEN is empty, auth is disabled (local/dev mode).
    """
    if not _DASHBOARD_API_TOKEN:
        return None

    provided = (
        request.headers.get("X-API-Token")
        or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        or (request.args.get("token") or "").strip()
    )

    if provided != _DASHBOARD_API_TOKEN:
        return jsonify({"error": "Unauthorized: token faltante o invalido"}), 401
    return None
