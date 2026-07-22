"""Capture ADR-059 Phase 2 review exception drawer screenshots via Playwright."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "corpsite-ui" / "adr059-phase2-ui-verify"
BASE_URL = os.environ.get("CAPTURE_BASE_URL", "http://localhost:3000").rstrip("/")
DEV_USER_ID = int(os.environ.get("CAPTURE_DEV_USER_ID", "34"))
BATCH_ID = int(os.environ["CAPTURE_BATCH_ID"]) if os.environ.get("CAPTURE_BATCH_ID") else None


def mint_dev_jwt(user_id: int) -> str:
    cmd = [
        str(REPO_ROOT / "venv" / "Scripts" / "python.exe"),
        "-c",
        f"from app.auth import create_access_token; print(create_access_token({user_id}))",
    ]
    return subprocess.check_output(cmd, cwd=REPO_ROOT, text=True).strip()


def resolve_batch_id() -> int:
    if BATCH_ID is not None:
        return BATCH_ID
    sys.path.insert(0, str(REPO_ROOT))
    from app.db.engine import engine
    from app.services.hr_import_review_exception_detail_service import list_review_exceptions
    from sqlalchemy import text

    with engine.connect() as conn:
        batch_id = conn.execute(
            text("SELECT batch_id FROM public.hr_import_batches ORDER BY batch_id DESC LIMIT 1")
        ).scalar_one()
        batch_id = int(batch_id)
        items = list_review_exceptions(conn, batch_id)["items"]
        if items:
            return batch_id
    raise RuntimeError("No review exceptions found")


def pick_exception_key(batch_id: int, diff_status: str) -> str | None:
    sys.path.insert(0, str(REPO_ROOT))
    from app.db.engine import engine
    from app.services.hr_import_review_exception_detail_service import list_review_exceptions

    with engine.connect() as conn:
        payload = list_review_exceptions(conn, batch_id, diff_status=diff_status, limit=1)
    items = payload.get("items") or []
    return items[0]["exception_key"] if items else None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    batch_id = resolve_batch_id()
    token = mint_dev_jwt(DEV_USER_ID)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        page.evaluate(
            """({ token, login }) => {
              localStorage.setItem('access_token', token);
              localStorage.setItem('login', login);
            }""",
            {"token": token, "login": "pall_head_34"},
        )

        captured: list[str] = []
        for diff_status, filename in [
            ("NEW", "01-review-exception-new.png"),
            ("CONFLICT", "02-review-exception-conflict.png"),
            ("REMOVED", "03-review-exception-removed.png"),
        ]:
            exception_key = pick_exception_key(batch_id, diff_status)
            if not exception_key:
                print(f"Skip {diff_status}: no exception", file=sys.stderr)
                continue
            url = (
                f"{BASE_URL}/directory/personnel/import/{batch_id}/review"
                f"?adr059_exception={exception_key}"
            )
            page.goto(url, wait_until="networkidle", timeout=120_000)
            page.wait_for_selector('[data-testid="import-review-exception-drawer"]', timeout=30_000)
            page.wait_for_timeout(800)
            target = OUT_DIR / filename
            page.screenshot(path=str(target), full_page=True)
            captured.append(filename)
            print(f"Saved {filename} ({exception_key})")

        browser.close()

    print(json.dumps({"batch_id": batch_id, "out_dir": str(OUT_DIR), "captured": captured}, ensure_ascii=False))


if __name__ == "__main__":
    main()
