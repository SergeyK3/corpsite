"""End-to-end verification for applicant intake link persistence (local demo)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.personnel_intake.domain.models import empty_intake_draft_payload  # noqa: E402
from tests.conftest import auth_headers  # noqa: E402


def _redact_path(path: str | None) -> str:
    raw = str(path or "").strip()
    if not raw.startswith("/intake/"):
        return raw or "—"
    token = raw.removeprefix("/intake/")
    if len(token) <= 8:
        return raw
    return f"/intake/{token[:8]}…"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-revoke",
        action="store_true",
        help="Leave the submitted link active for manual browser checks.",
    )
    args = parser.parse_args()

    client = TestClient(app)
    headers = auth_headers(34)
    report: dict[str, object] = {"steps": []}
    artifact = ROOT / ".demo-intake-verify.json"

    def step(name: str, ok: bool, detail: str = "") -> None:
        report["steps"].append({"name": name, "ok": ok, "detail": detail})
        mark = "OK" if ok else "FAIL"
        print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))

    reg = client.post(
        "/directory/personnel-applications",
        json={
            "iin": f"8{uuid4().int % 10_000_000_000_000:011d}"[:12],
            "full_name": "Demo Intake Applicant",
            "application_received_at": "2026-07-20",
            "vacancy_check_status": "confirmed_visually",
            "idempotency_key": f"demo-verify-{uuid4().hex}",
        },
        headers=headers,
    )
    if reg.status_code != 200:
        step("register applicant", False, reg.text[:200])
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    app_id = int(reg.json()["application_id"])
    step("register applicant", True, f"application_id={app_id}")

    issue = client.post(f"/directory/personnel-applications/{app_id}/intake-link", headers=headers)
    ok_issue = issue.status_code == 200 and issue.json().get("intake_url_path")
    path = issue.json().get("intake_url_path") if ok_issue else None
    step("issue intake link", ok_issue, _redact_path(path))

    reissue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link/reissue",
        headers=headers,
    )
    ok_reissue = reissue.status_code == 200 and reissue.json().get("reissued") is True
    path = reissue.json().get("intake_url_path") if ok_reissue else path
    step("reissue intake link", ok_reissue, _redact_path(path))

    lst = client.get("/directory/personnel-applications", params={"limit": 20}, headers=headers)
    row = next((item for item in lst.json().get("items", []) if item.get("application_id") == app_id), None)
    ok_list = (
        lst.status_code == 200
        and row is not None
        and row.get("intake_link_display_state") == "active"
        and bool(row.get("intake_url_path"))
    )
    step(
        "list API exposes intake_url_path",
        ok_list,
        f"display_state={row.get('intake_link_display_state') if row else None}",
    )

    active = client.get(
        f"/directory/personnel-applications/{app_id}/intake-link/active",
        headers=headers,
    )
    ok_active = active.status_code == 200 and active.json().get("intake_url_path")
    path = active.json().get("intake_url_path") if ok_active else path
    step("active endpoint persists link", ok_active, _redact_path(path))

    token = str(path or "").removeprefix("/intake/").strip()
    open_resp = client.get(f"/intake/{token}")
    step("open intake (anonymous)", open_resp.status_code == 200, f"status={open_resp.status_code}")

    payload = empty_intake_draft_payload()
    payload["personal"]["last_name"] = "Иванов"
    payload["personal"]["first_name"] = "Иван"
    payload["contacts"]["mobile_phone"] = "+77001234567"
    payload["education"] = [
        {
            "institution": "КазНУ",
            "year_from": "2018",
            "year_to": "2022",
            "specialty": "IT",
            "qualification": "Бакалавр",
            "diploma_number": "123",
        }
    ]
    save = client.patch(f"/intake/{token}", json={"payload": payload})
    step("autosave draft", save.status_code == 200, f"status={save.status_code}")

    submit = client.post(f"/intake/{token}/submit", json={"payload": payload})
    step("submit intake", submit.status_code == 200, f"status={submit.status_code}")

    active_after = client.get(
        f"/directory/personnel-applications/{app_id}/intake-link/active",
        headers=headers,
    )
    ok_submitted = (
        active_after.status_code == 200
        and active_after.json().get("display_state") == "submitted"
        and active_after.json().get("intake_url_path")
    )
    step(
        "submitted keeps recoverable link",
        ok_submitted,
        _redact_path(active_after.json().get("intake_url_path")),
    )

    readonly = client.get(f"/intake/{token}")
    readonly_ok = readonly.status_code == 200 and readonly.json().get("read_only") is True
    step("intake read-only after submit", readonly_ok, f"read_only={readonly.json().get('read_only')}")

    artifact.write_text(
        json.dumps(
            {
                "application_id": app_id,
                "intake_url_path": path,
                "display_state_after_submit": active_after.json().get("display_state"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if args.skip_revoke:
        failed = [s for s in report["steps"] if not s["ok"]]
        print(f"\nSummary: {len(report['steps']) - len(failed)}/{len(report['steps'])} passed (revoke skipped)")
        return 0 if not failed else 1

    revoke = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link/revoke",
        headers=headers,
    )
    step("revoke link", revoke.status_code == 200, f"status={revoke.status_code}")

    active_revoked = client.get(
        f"/directory/personnel-applications/{app_id}/intake-link/active",
        headers=headers,
    )
    ok_revoked = (
        active_revoked.status_code == 200
        and active_revoked.json().get("display_state") == "revoked"
        and not active_revoked.json().get("intake_url_path")
    )
    step(
        "revoked hides copy/open path",
        ok_revoked,
        f"display_state={active_revoked.json().get('display_state')}",
    )

    denied = client.get(f"/intake/{token}")
    step("revoked token denied", denied.status_code == 403, f"status={denied.status_code}")

    failed = [s for s in report["steps"] if not s["ok"]]
    print(f"\nSummary: {len(report['steps']) - len(failed)}/{len(report['steps'])} passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
