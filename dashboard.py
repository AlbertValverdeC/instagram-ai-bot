#!/usr/bin/env python3
"""
Dashboard Web — Panel de control simple para Instagram AI Bot.

Usage:
    python dashboard.py              # http://localhost:8000
    python dashboard.py --port 8080  # http://localhost:8080
"""

from __future__ import annotations

import argparse
import os

from dashboard import app

if __name__ == "__main__":
    default_port = int(os.getenv("PORT", "8000"))
    default_host = os.getenv("HOST", "127.0.0.1")
    parser = argparse.ArgumentParser(description="IG AI Bot — Dashboard Web")
    parser.add_argument("--port", type=int, default=default_port, help=f"Port (default: {default_port})")
    parser.add_argument("--host", default=default_host, help=f"Host (default: {default_host})")
    args = parser.parse_args()

    print("\n  IG AI Bot — Panel de Control")
    print(f"  http://{args.host}:{args.port}\n")

    app.run(host=args.host, port=args.port, debug=False)
