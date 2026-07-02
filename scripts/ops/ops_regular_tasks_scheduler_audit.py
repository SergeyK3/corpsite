#!/usr/bin/env python3
"""Read-only operational audit for regular-tasks automatic scheduler.

Run on VPS from repo root:

  set -a && source .env && set +a
  .venv/bin/python scripts/ops/ops_regular_tasks_scheduler_audit.py

Optional endpoint probe (uses INTERNAL_API_TOKEN from .env, dry_run=true):

  .venv/bin/python scripts/ops/ops_regular_tasks_scheduler_audit.py --probe-endpoint

Optional JSON output:

  .venv/bin/python scripts/ops/ops_regular_tasks_scheduler_audit.py --json
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


def _collect_infrastructure(report: AuditReport) -> None:
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
    elif infra.get("crontab_hits"):
        report.add(
            "scheduler_timer_installed",
            "warn",
            f"no systemd timer, but crontab entries found: {len(infra['crontab_hits'])}",
        )
    else:
        report.add(
            "scheduler_timer_installed",
            "fail",
            "no corpsite-regular-tasks.timer and no crontab entry for regular tasks",
        )


def _collect_journal(report: AuditReport) -> None:
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
        report.add("journal_automatic_runs_present", "skip", f"database unavailable: {exc}")
        report.add("cron_overdue", "skip", "scheduler-status unavailable without database")
        return

    report.scheduler_status = status_payload
    report.journal = {
        "recent_automatic_runs": automatic[:10],
        "last_automatic_run": automatic[0] if automatic else None,
        "automatic_runs_in_journal": int(status_payload.get("automatic_runs_in_journal") or 0),
    }

    if automatic:
        report.add(
            "journal_automatic_runs_present",
            "pass",
            f"last automatic run_id={automatic[0]['run_id']} started_at={automatic[0]['started_at']}",
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
    code, out = _run(
        [
            "curl",
            "-sS",
            "-o",
            "-",
            "-w",
            "\n__HTTP_CODE__:%{http_code}",
            "-X",
            "POST",
            f"{backend}/internal/regular-tasks/run",
            "-H",
            "Content-Type: application/json",
            "-H",
            f"X-Internal-Api-Token: {token}",
            "-H",
            f"X-User-Id: {cron_user}",
            "-d",
            payload,
        ],
        timeout=60,
    )

    http_code = 0
    body = out
    if "__HTTP_CODE__:" in out:
        body, _, tail = out.rpartition("\n__HTTP_CODE__:")
        try:
            http_code = int(tail.strip())
        except ValueError:
            http_code = 0

    if http_code == 200:
        report.add(
            "endpoint_probe",
            "pass" if dry_run else "warn",
            f"HTTP 200 dry_run={dry_run}; body={body[:240]!r}",
        )
        return

    report.add("endpoint_probe", "fail", f"HTTP {http_code}; body={body[:240]!r}")


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
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args()

    report = AuditReport(generated_at=datetime.now(timezone.utc).isoformat())
    report.environment = _collect_env_snapshot()

    if (os.getenv("INTERNAL_API_TOKEN") or "").strip() in {"", "change-me"}:
        report.add("internal_api_token", "fail", "INTERNAL_API_TOKEN missing or placeholder")
    else:
        report.add("internal_api_token", "pass", report.environment["INTERNAL_API_TOKEN"])

    _collect_infrastructure(report)
    _validate_cron_user(report)
    _collect_journal(report)

    if args.probe_endpoint or args.probe_live:
        _probe_endpoint(report, dry_run=not args.probe_live)

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        _print_human(report)

    return 1 if report.has_failures() else 0


if __name__ == "__main__":
    raise SystemExit(main())
