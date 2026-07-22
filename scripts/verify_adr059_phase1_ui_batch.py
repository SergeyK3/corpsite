"""Functional verification for ADR-059 Phase 1 UI batch via API (compute-diff hook)."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

from tests.conftest import auth_headers

BATCH_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1357
BASE = "http://localhost:8000"


def api(method: str, path: str, body: dict | None = None) -> dict:
    headers = auth_headers(34)
    headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE}{path}", method=method, headers=headers)
    if body is not None:
        req.data = json.dumps(body).encode("utf-8")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {payload}") from exc


def main() -> None:
    before = api("GET", f"/directory/personnel/import/batches/{BATCH_ID}")
    progress = api(
        "GET",
        f"/directory/personnel/import/batches/{before['import_code']}/complete-review",
    )
    print(
        "BEFORE",
        json.dumps(
            {
                "batch_id": BATCH_ID,
                "import_code": before["import_code"],
                "status": before["status"],
                "review_progress": progress.get("review_progress"),
                "blockers": [item["code"] for item in progress.get("blockers", [])],
            },
            ensure_ascii=False,
            indent=2,
        ),
    )

    diff = api("POST", f"/directory/personnel/import/batches/{BATCH_ID}/compute-diff")
    after = api("GET", f"/directory/personnel/import/batches/{BATCH_ID}")
    progress_after = api(
        "GET",
        f"/directory/personnel/import/batches/{after['import_code']}/complete-review",
    )
    print(
        "AFTER",
        json.dumps(
            {
                "batch_id": BATCH_ID,
                "import_code": after["import_code"],
                "status": after["status"],
                "diff_summary": diff.get("summary"),
                "review_visibility": diff.get("review_visibility"),
                "auto_complete_review": diff.get("auto_complete_review"),
                "review_progress": progress_after.get("review_progress"),
                "blockers": [item["code"] for item in progress_after.get("blockers", [])],
            },
            ensure_ascii=False,
            indent=2,
        ),
    )


if __name__ == "__main__":
    main()
