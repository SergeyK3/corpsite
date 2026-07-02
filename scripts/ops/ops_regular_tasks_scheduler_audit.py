#!/usr/bin/env python3
"""Read-only operational audit for regular-tasks automatic scheduler.

Run on VPS from repo root:

  set -a && source .env && set +a
  .venv/bin/python scripts/ops/ops_regular_tasks_scheduler_audit.py

Optional endpoint probe (uses INTERNAL_API_TOKEN from .env, dry_run=true):

  .venv/bin/python scripts/ops/ops_regular_tasks_scheduler_audit.py --probe-endpoint

Optional post-deploy smoke (safe: dry_run probe + routing check, no task creation):

  .venv/bin/python scripts/ops/ops_regular_tasks_scheduler_audit.py --post-deploy-smoke

Or via deploy pipeline (automatic after backend health check):

  sudo ./scripts/ops/scheduler_post_deploy_smoke.sh
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.engine import engine
from app.services.regular_task_scheduler_status import (
    build_regular_task_scheduler_status,
    is_automatic_live_run,
)
from app.services.regular_tasks_service import (
    IGNORE_TIME_GATE_ENV,
    SYSTEM_USER_ID,
    TZ_OFFSET_HOURS,
)


@dataclass
class CheckResult:
    name: str
    status: str  # pass | fail | warn | skip
    detail: str = ""


@dataclass
class AuditReport:
    generated_at: str
    checks: List[CheckResult] = field(default_factory=list)
    infrastructure: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    journal: Dict[str, Any] = field(default_factory=dict)
    scheduler_status: Dict[str, Any] = field(default_factory=dict)

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.checks.append(CheckResult(name=name, status=status, detail=detail))

    def has_failures(self) -> bool:
        return any(c.status == "fail" for c in self.checks)


SCHEDULER_STATUS_REQUIRED_KEYS = (
    "automatic_enabled",
    "status",
    "status_label",
    "status_explanation",
    "observation_window_days",
    "last_result_label",
    "hint",
    "checked_at",
)


def validate_scheduler_status_payload(payload: Dict[str, Any]) -> Optional[str]:
    """Return error message when payload does not match scheduler-status contract."""
    if not isinstance(payload, dict):
        return "response is not a JSON object"
    missing = [key for key in SCHEDULER_STATUS_REQUIRED_KEYS if key not in payload]
    if missing:
        return f"missing keys: {', '.join(missing)}"
    if not isinstance(payload.get("status"), str) or not payload["status"].strip():
        return "status must be a non-empty string"
    if not isinstance(payload.get("checked_at"), str) or not payload["checked_at"].strip():
        return "checked_at must be a non-empty string"
    return None


def _run(cmd: list[str], *, timeout: int = 20) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        cwd=str(ROOT),
    )
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, out


def _http_request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[str] = None,
    timeout: int = 30,
) -> tuple[int, str]:
    if not shutil.which("curl"):
        return 0, "curl not available"

    cmd = [
        "curl",
        "-sS",
        "-o",
        "-",
        "-w",
        "\n__HTTP_CODE__:%{http_code}",
        "-X",
        method.upper(),
        url,
    ]
    for key, val in (headers or {}).items():
        cmd.extend(["-H", f"{key}: {val}"])
    if body is not None:
        cmd.extend(["-d", body])

    _, out = _run(cmd, timeout=timeout)
    if "__HTTP_CODE__:" not in out:
        return 0, out[:500]

    body_text, _, tail = out.rpartition("\n__HTTP_CODE__:")
    try:
        return int(tail.strip()), body_text
    except ValueError:
        return 0, out[:500]


def _mask(value: Optional[str]) -> str:
    raw = (value or "").strip()
    if not raw:
        return "MISSING"
    if raw in {"change-me", "dev-secret-change-me"}:
        return "PLACEHOLDER"
    return f"set (len={len(raw)})"


def _collect_env_snapshot() -> Dict[str, Any]:
    return {
        "INTERNAL_API_TOKEN": _mask(os.getenv("INTERNAL_API_TOKEN")),
        "REGULAR_TASKS_CRON_USER_ID": (os.getenv("REGULAR_TASKS_CRON_USER_ID") or "").strip() or "MISSING",
        "REGULAR_TASKS_SYSTEM_USER_ID": str(SYSTEM_USER_ID),
        "REGULAR_TASKS_TZ_OFFSET_HOURS": str(TZ_OFFSET_HOURS),
        "REGULAR_TASKS_IGNORE_TIME_GATE": bool(IGNORE_TIME_GATE_ENV),
        "BACKEND_URL": (os.getenv("BACKEND_URL") or "http://127.0.0.1:8000").strip(),
    }


def _collect_infrastructure(report: AuditReport, *, post_deploy: bool = False) -> None:
    infra: Dict[str, Any] = {}

    if shutil.which("systemctl"):
        code, timers = _run(["systemctl", "list-timers", "--all", "--no-pager"])
        infra["systemd_list_timers_exit"] = code
        infra["systemd_timers_matching_regular_tasks"] = [
            line for line in timers.splitlines() if "regular" in line.lower()
        ]

        for unit in (
            "corpsite-regular-tasks.timer",
            "corpsite-regular-tasks.service",
            "corpsite-backend.service",
        ):
            _, active = _run(["systemctl", "is-active", unit])
            _, enabled = _run(["systemctl", "is-enabled", unit])
            infra[f"{unit}_active"] = active.strip()
            infra[f"{unit}_enabled"] = enabled.strip()

        _, journal = _run(
            ["journalctl", "-u", "corpsite-regular-tasks.service", "-n", "30", "--no-pager", "-o", "cat"]
        )
        infra["corpsite_regular_tasks_journal_tail"] = journal[:4000]
    else:
        report.add("systemd", "skip", "systemctl not available on this host")

    crontab_hits: list[str] = []
    if shutil.which("crontab"):
        for user in ("root", os.getenv("USER") or ""):
            if not user:
                continue
            code, out = _run(["crontab", "-l", "-u", user])
            if code != 0:
                continue
            for line in out.splitlines():
                if "regular-tasks" in line or "run_regular_tasks_cron" in line:
                    crontab_hits.append(f"{user}: {line.strip()}")
    infra["crontab_hits"] = crontab_hits

    repo_script = ROOT / "scripts" / "ops" / "run_regular_tasks_cron.sh"
    repo_service = ROOT / "deploy" / "systemd" / "corpsite-regular-tasks.service"
    repo_timer = ROOT / "deploy" / "systemd" / "corpsite-regular-tasks.timer"
    infra["repo_invoke_script_exists"] = repo_script.is_file()
    infra["repo_systemd_units_exist"] = repo_service.is_file() and repo_timer.is_file()

    report.infrastructure = infra

    if infra.get("corpsite-regular-tasks.timer_enabled") == "enabled":
        report.add("scheduler_timer_installed", "pass", "corpsite-regular-tasks.timer is enabled")
    elif infra.get("crontab_hits") and not post_deploy:
        report.add(
            "scheduler_timer_installed",
            "warn",
            f"no systemd timer, but crontab entries found: {len(infra['crontab_hits'])}",
        )
    elif infra.get("crontab_hits") and post_deploy:
        report.add(
            "scheduler_timer_installed",
            "fail",
            "post-deploy smoke requires corpsite-regular-tasks.timer (crontab-only is not enough)",
        )
    else:
        report.add(
            "scheduler_timer_installed",
            "fail",
            "no corpsite-regular-tasks.timer and no crontab entry for regular tasks",
        )

    timer_active = (infra.get("corpsite-regular-tasks.timer_active") or "").strip()
    if post_deploy and timer_active and timer_active != "active":
        report.add(
            "scheduler_timer_active",
            "fail",
            f"corpsite-regular-tasks.timer is-active={timer_active!r} (expected active/waiting)",
        )
    elif post_deploy and timer_active == "active":
        report.add("scheduler_timer_active", "pass", "corpsite-regular-tasks.timer is active (waiting)")


def _collect_journal(report: AuditReport, *, post_deploy: bool = False) -> None:
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT run_id, started_at, finished_at, status, stats, errors
                    FROM public.regular_task_runs
                    ORDER BY run_id DESC
                    LIMIT 50
                    """
                )
            ).mappings().all()

            automatic: list[dict[str, Any]] = []
            for row in rows:
                stats = row.get("stats") or {}
                if isinstance(stats, str):
                    try:
                        stats = json.loads(stats)
                    except json.JSONDecodeError:
                        stats = {}
                if not isinstance(stats, dict):
                    stats = {}
                if is_automatic_live_run(stats):
                    automatic.append(
                        {
                            "run_id": int(row["run_id"]),
                            "started_at": str(row["started_at"]),
                            "status": str(row["status"]),
                            "trigger_source": stats.get("trigger_source"),
                            "errors": stats.get("errors"),
                            "run_kind": stats.get("run_kind"),
                        }
                    )

            status_payload = build_regular_task_scheduler_status(conn)
    except Exception as exc:
        db_status = "fail" if post_deploy else "skip"
        report.add("journal_automatic_runs_present", db_status, f"database unavailable: {exc}")
        report.add("cron_overdue", db_status, "scheduler-status unavailable without database")
        if post_deploy:
            report.add("scheduler_status_contract", "fail", f"database unavailable: {exc}")
        return

    report.scheduler_status = status_payload
    report.journal = {
        "recent_automatic_runs": automatic[:10],
        "last_automatic_run": automatic[0] if automatic else None,
        "automatic_runs_in_journal": int(status_payload.get("automatic_runs_in_journal") or 0),
    }

    contract_err = validate_scheduler_status_payload(status_payload)
    if contract_err:
        report.add("scheduler_status_contract", "fail", contract_err)
    else:
        report.add(
            "scheduler_status_contract",
            "pass",
            f"status={status_payload.get('status')} (computed via DB)",
        )

    if automatic:
        report.add(
            "journal_automatic_runs_present",
            "pass",
            f"last automatic run_id={automatic[0]['run_id']} started_at={automatic[0]['started_at']}",
        )
    elif post_deploy:
        report.add(
            "journal_automatic_runs_present",
            "warn",
            "no automatic live runs in regular_task_runs (historical gap — timer restore does not backfill)",
        )
    else:
        report.add("journal_automatic_runs_present", "fail", "no automatic live runs in regular_task_runs")

    if status_payload.get("is_cron_overdue"):
        report.add(
            "cron_overdue",
            "warn",
            f"overdue_days={status_payload.get('cron_overdue_days')} expected={status_payload.get('expected_next_run_label')}",
        )
    else:
        report.add("cron_overdue", "pass", "scheduler status does not report cron overdue")


def _validate_cron_user(report: AuditReport) -> None:
    cron_user_raw = (os.getenv("REGULAR_TASKS_CRON_USER_ID") or "").strip()
    if not cron_user_raw:
        report.add("cron_user_configured", "fail", "REGULAR_TASKS_CRON_USER_ID is missing")
        return

    try:
        cron_user_id = int(cron_user_raw)
    except ValueError:
        report.add("cron_user_configured", "fail", f"invalid REGULAR_TASKS_CRON_USER_ID={cron_user_raw!r}")
        return

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT user_id, role_id, is_active, login
                    FROM public.users
                    WHERE user_id = :uid
                    """
                ),
                {"uid": cron_user_id},
            ).mappings().first()
    except Exception as exc:
        report.add("cron_user_exists", "skip", f"database unavailable: {exc}")
        return

    if not row:
        report.add("cron_user_exists", "fail", f"user_id={cron_user_id} not found")
        return

    if not bool(row.get("is_active", True)):
        report.add("cron_user_exists", "fail", f"user_id={cron_user_id} is inactive")
        return

    role_id = int(row.get("role_id") or 0)
    if role_id != 2:
        report.add(
            "cron_user_system_admin",
            "fail",
            f"user_id={cron_user_id} role_id={role_id} (expected system admin role_id=2)",
        )
        return

    report.add(
        "cron_user_system_admin",
        "pass",
        f"user_id={cron_user_id} login={row.get('login')} role_id=2 active=true",
    )


def _probe_endpoint(report: AuditReport, *, dry_run: bool) -> None:
    token = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
    cron_user = (os.getenv("REGULAR_TASKS_CRON_USER_ID") or "").strip()
    backend = (os.getenv("BACKEND_URL") or "http://127.0.0.1:8000").rstrip("/")

    if not token or token == "change-me":
        report.add("endpoint_probe", "fail", "INTERNAL_API_TOKEN missing or placeholder")
        return
    if not cron_user:
        report.add("endpoint_probe", "fail", "REGULAR_TASKS_CRON_USER_ID missing")
        return

    if not shutil.which("curl"):
        report.add("endpoint_probe", "skip", "curl not available")
        return

    payload = json.dumps({"dry_run": dry_run})
    http_code, body = _http_request(
        "POST",
        f"{backend}/internal/regular-tasks/run",
        headers={
            "Content-Type": "application/json",
            "X-Internal-Api-Token": token,
            "X-User-Id": cron_user,
        },
        body=payload,
        timeout=60,
    )

    if http_code == 200:
        report.add(
            "endpoint_probe",
            "pass" if dry_run else "warn",
            f"HTTP 200 dry_run={dry_run}; body={body[:240]!r}",
        )
        return

    report.add("endpoint_probe", "fail", f"HTTP {http_code}; body={body[:240]!r}")


def _probe_scheduler_status_route(report: AuditReport) -> None:
    backend = (os.getenv("BACKEND_URL") or "http://127.0.0.1:8000").rstrip("/")
    url = f"{backend}/regular-tasks/scheduler-status"

    if not shutil.which("curl"):
        report.add("scheduler_status_routing", "skip", "curl not available")
        return

    http_code, body = _http_request("GET", url)
    if http_code == 422 and ("int_parsing" in body or "regular_task_id" in body):
        report.add(
            "scheduler_status_routing",
            "fail",
            f"HTTP 422 — route shadowed by /regular-tasks/{{id}}: {body[:240]!r}",
        )
        return

    if http_code == 401:
        report.add(
            "scheduler_status_routing",
            "pass",
            "HTTP 401 (auth required; path resolves, not 422)",
        )
        return

    if http_code == 200:
        contract_err = None
        try:
            contract_err = validate_scheduler_status_payload(json.loads(body))
        except json.JSONDecodeError:
            contract_err = "response is not valid JSON"
        if contract_err:
            report.add("scheduler_status_routing", "fail", f"HTTP 200 but invalid payload: {contract_err}")
        else:
            report.add("scheduler_status_routing", "pass", "HTTP 200 with valid scheduler-status JSON")
        return

    report.add("scheduler_status_routing", "fail", f"HTTP {http_code}; body={body[:240]!r}")


def _probe_scheduler_status_http_contract(report: AuditReport) -> None:
    login = (os.getenv("CORPSITE_SMOKE_ADMIN_LOGIN") or "").strip()
    password = (os.getenv("CORPSITE_SMOKE_ADMIN_PASSWORD") or "").strip()
    if not login or not password:
        report.add(
            "scheduler_status_http_contract",
            "skip",
            "set CORPSITE_SMOKE_ADMIN_LOGIN and CORPSITE_SMOKE_ADMIN_PASSWORD for authenticated HTTP check",
        )
        return

    if not shutil.which("curl"):
        report.add("scheduler_status_http_contract", "skip", "curl not available")
        return

    backend = (os.getenv("BACKEND_URL") or "http://127.0.0.1:8000").rstrip("/")
    url = f"{backend}/regular-tasks/scheduler-status"

    login_code, login_body = _http_request(
        "POST",
        f"{backend}/auth/login",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"login": login, "password": password}),
    )
    if login_code != 200:
        report.add("scheduler_status_http_contract", "fail", f"smoke admin login HTTP {login_code}")
        return

    try:
        token = json.loads(login_body).get("access_token")
    except json.JSONDecodeError:
        report.add("scheduler_status_http_contract", "fail", "smoke admin login returned invalid JSON")
        return

    if not token:
        report.add("scheduler_status_http_contract", "fail", "smoke admin login returned no access_token")
        return

    http_code, body = _http_request(
        "GET",
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    if http_code != 200:
        report.add("scheduler_status_http_contract", "fail", f"authenticated GET HTTP {http_code}")
        return

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        report.add("scheduler_status_http_contract", "fail", "authenticated response is not valid JSON")
        return

    contract_err = validate_scheduler_status_payload(payload)
    if contract_err:
        report.add("scheduler_status_http_contract", "fail", contract_err)
    else:
        report.add(
            "scheduler_status_http_contract",
            "pass",
            f"status={payload.get('status')} (authenticated HTTP)",
        )


def _print_human(report: AuditReport) -> None:
    print(f"Regular tasks scheduler audit @ {report.generated_at}")
    print()

    print("== Environment (secrets masked) ==")
    for key, value in report.environment.items():
        print(f"  {key}: {value}")
    print()

    print("== Infrastructure ==")
    infra = report.infrastructure
    print(f"  repo invoke script: {infra.get('repo_invoke_script_exists')}")
    print(f"  repo systemd units: {infra.get('repo_systemd_units_exist')}")
    print(f"  corpsite-regular-tasks.timer enabled: {infra.get('corpsite-regular-tasks.timer_enabled', 'n/a')}")
    print(f"  crontab hits: {infra.get('crontab_hits') or 'none'}")
    print()

    print("== Journal / scheduler-status ==")
    journal = report.journal
    last = journal.get("last_automatic_run")
    if last:
        print(
            f"  last automatic: run_id={last['run_id']} started_at={last['started_at']} status={last['status']}"
        )
    else:
        print("  last automatic: none")
    print(f"  automatic_runs_in_journal: {journal.get('automatic_runs_in_journal')}")
    status = report.scheduler_status
    print(f"  panel status: {status.get('status')} / {status.get('status_label')}")
    print(f"  explanation: {status.get('status_explanation')}")
    if status.get("is_cron_overdue"):
        print(
            f"  overdue: {status.get('cron_overdue_days')} days; expected {status.get('expected_next_run_label')}"
        )
    print()

    print("== Checks ==")
    for check in report.checks:
        print(f"  [{check.status.upper():4}] {check.name}: {check.detail}")
    print()

    if report.has_failures():
        print("RESULT: FAIL — see failed checks above")
    else:
        print("RESULT: PASS (warnings may still require attention)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit regular-tasks automatic scheduler")
    parser.add_argument("--probe-endpoint", action="store_true", help="POST dry_run to /internal/regular-tasks/run")
    parser.add_argument("--probe-live", action="store_true", help="POST live run (use with care on production)")
    parser.add_argument(
        "--post-deploy-smoke",
        action="store_true",
        help="Post-deploy safe mode: dry_run probe + scheduler-status routing (no task creation)",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args()

    post_deploy = bool(args.post_deploy_smoke)
    if post_deploy and args.probe_live:
        print("ERROR: --post-deploy-smoke cannot be combined with --probe-live", file=sys.stderr)
        return 2

    report = AuditReport(generated_at=datetime.now(timezone.utc).isoformat())
    report.environment = _collect_env_snapshot()

    if (os.getenv("INTERNAL_API_TOKEN") or "").strip() in {"", "change-me"}:
        report.add("internal_api_token", "fail", "INTERNAL_API_TOKEN missing or placeholder")
    else:
        report.add("internal_api_token", "pass", report.environment["INTERNAL_API_TOKEN"])

    _collect_infrastructure(report, post_deploy=post_deploy)
    _validate_cron_user(report)
    _collect_journal(report, post_deploy=post_deploy)

    if post_deploy:
        _probe_endpoint(report, dry_run=True)
        _probe_scheduler_status_route(report)
        _probe_scheduler_status_http_contract(report)
    elif args.probe_endpoint or args.probe_live:
        _probe_endpoint(report, dry_run=not args.probe_live)

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        _print_human(report)

    return 1 if report.has_failures() else 0


if __name__ == "__main__":
    raise SystemExit(main())
