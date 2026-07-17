#!/usr/bin/env python3
"""Ops cron helper: run onboarding task reminders (WP-ONBOARDING-002)."""
from __future__ import annotations

import os
import sys

import httpx


def main() -> int:
    base_url = (os.getenv("CORPSITE_API_BASE_URL") or "http://127.0.0.1:8000").rstrip("/")
    token = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
    if not token:
        print("INTERNAL_API_TOKEN is required", file=sys.stderr)
        return 2
    url = f"{base_url}/internal/onboarding/reminders/run"
    resp = httpx.post(url, headers={"X-Internal-Api-Token": token}, timeout=60.0)
    print(resp.status_code, resp.text)
    return 0 if resp.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
