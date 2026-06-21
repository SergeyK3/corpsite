#!/usr/bin/env python3
"""OPS-007b — read-only VPS Telegram validation (no sends, no mutations).

Run on VPS from repo root after OPS-007a deploy:

  set -a && source .env && set +a
  .venv/bin/python scripts/ops/ops007b_vps_telegram_validation.py

Optional remote route probe (no DB, no token required for negative checks):

  .venv/bin/python scripts/ops/ops007b_vps_telegram_validation.py \\
    --api-base https://mmc.004.kz/api --skip-systemd --skip-db
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INTERNAL_ROUTES: list[tuple[str, str]] = [
    ("POST", "/internal/bot/tg/resolve"),
    ("POST", "/internal/bot/tg/unbind"),
    ("GET", "/internal/bot/tasks"),
    ("GET", "/internal/bot/tasks/me/events"),
]


@dataclass
class CheckResult:
    name: str
    status: str  # pass | fail | skip | warn
    detail: str = ""


@dataclass
class ValidationReport:
    mode: str
    api_base: str
    checks: List[CheckResult] = field(default_factory=list)
    integrity_counts: Dict[str, Any] = field(default_factory=dict)
    systemd: Dict[str, Any] = field(default_factory=dict)
    journal_tail: Dict[str, str] = field(default_factory=dict)

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.checks.append(CheckResult(name=name, status=status, detail=detail))

    def passed(self) -> bool:
        return all(c.status in ("pass", "skip", "warn") for c in self.checks)


def _http_probe_curl(method: str, url: str, headers: Optional[Dict[str, str]] = None) -> tuple[int, str]:
    cmd = ["curl", "-sS", "-o", "-", "-w", "\n__HTTP_CODE__:%{http_code}", "-X", method.upper(), url]
    for key, val in (headers or {}).items():
        cmd.extend(["-H", f"{key}: {val}"])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=20)
    raw = (proc.stdout or "") + (proc.stderr or "")
    if "__HTTP_CODE__:" in raw:
        body, _, tail = raw.rpartition("\n__HTTP_CODE__:")
        try:
            return int(tail.strip()), body[:500]
        except ValueError:
            return 0, raw[:500]
    return 0, raw[:500] or f"curl exit {proc.returncode}"


def _http_probe(method: str, url: str, headers: Optional[Dict[str, str]] = None) -> tuple[int, str]:
    if shutil.which("curl"):
        return _http_probe_curl(method, url, headers)
    req = Request(url, method=method.upper(), headers=headers or {})
    try:
        with urlopen(req, timeout=15) as resp:
            body = resp.read(4096).decode("utf-8", errors="replace")
            return int(resp.status), body[:500]
    except HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        return int(exc.code), body[:500]
    except URLError as exc:
        return 0, str(exc.reason)


def _run_integrity_counts() -> Dict[str, Any]:
    script = ROOT / "scripts" / "ops" / "ops007_telegram_integrity_counts.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )
    counts: Dict[str, Any] = {"exit_code": proc.returncode, "raw_lines": []}
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, val = line.partition("=")
        counts["raw_lines"].append(line)
        if val.startswith("ERROR:"):
            counts[key] = {"error": val[6:]}
        else:
            try:
                counts[key] = int(val)
            except ValueError:
                counts[key] = val
    if proc.stderr:
        counts["stderr"] = proc.stderr.strip()[:1000]
    return counts


def _systemd_status(unit: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"unit": unit}
    for prop in ("ActiveState", "SubState", "Result", "MainPID"):
        proc = subprocess.run(
            ["systemctl", "show", unit, f"--property={prop}", "--value"],
            capture_output=True,
            text=True,
            check=False,
        )
        out[prop] = (proc.stdout or "").strip()
    proc = subprocess.run(
        ["systemctl", "is-active", unit],
        capture_output=True,
        text=True,
        check=False,
    )
    out["is_active_exit"] = proc.returncode
    return out


def _journal_recent(unit: str, lines: int = 80) -> str:
    proc = subprocess.run(
        ["journalctl", "-u", unit, "-n", str(lines), "--no-pager", "-o", "cat"],
        capture_output=True,
        text=True,
        check=False,
    )
    return (proc.stdout or proc.stderr or "").strip()


def _load_bindings_module():
    bindings_path = ROOT / "corpsite-bot" / "src" / "bot" / "storage" / "bindings.py"
    spec = importlib.util.spec_from_file_location("ops007b_bindings", bindings_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _startup_exception_scan(journal_text: str) -> list[str]:
    patterns = (
        r"Traceback \(most recent call last\)",
        r"ERROR",
        r"Exception",
        r"CRITICAL",
    )
    hits: list[str] = []
    for line in journal_text.splitlines():
        if any(re.search(p, line, re.IGNORECASE) for p in patterns):
            hits.append(line.strip())
    return hits[-10:]


def validate_routes(report: ValidationReport, api_base: str) -> None:
    base = api_base.rstrip("/")
    for method, path in INTERNAL_ROUTES:
        url = f"{base}{path}"
        code_none, body_none = _http_probe(method, url)
        code_tg, body_tg = _http_probe(
            method,
            url,
            headers={"X-Telegram-User-Id": "900007999"},
        )

        if code_none == 404:
            report.add(
                f"route_exists:{path}",
                "fail",
                f"HTTP 404 — OPS-007a not deployed or wrong api_base ({method} {url})",
            )
            continue

        if code_none != 403:
            report.add(
                f"route_token_guard:{path}",
                "fail",
                f"expected 403 without token, got {code_none}; body={body_none[:120]!r}",
            )
        else:
            report.add(
                f"route_token_guard:{path}",
                "pass",
                f"403 without X-Internal-Api-Token",
            )

        if code_tg != 403:
            report.add(
                f"route_token_guard_tg_only:{path}",
                "fail",
                f"expected 403 with TG header only, got {code_tg}; body={body_tg[:120]!r}",
            )
        else:
            report.add(
                f"route_token_guard_tg_only:{path}",
                "pass",
                "403 with X-Telegram-User-Id only (token still required)",
            )


def validate_legacy_json(report: ValidationReport) -> None:
    legacy_env = (os.getenv("TELEGRAM_LEGACY_JSON_BINDINGS") or "").strip()
    if legacy_env:
        report.add(
            "legacy_json_bindings_env",
            "fail",
            f"TELEGRAM_LEGACY_JSON_BINDINGS={legacy_env!r} — must be unset on production",
        )
    else:
        report.add("legacy_json_bindings_env", "pass", "TELEGRAM_LEGACY_JSON_BINDINGS unset")

    mod = _load_bindings_module()
    if mod.legacy_json_bindings_enabled():
        report.add("legacy_json_bindings_runtime", "fail", "legacy_json_bindings_enabled() is True")
    elif mod.get_binding(12345) is not None:
        report.add("legacy_json_bindings_runtime", "fail", "get_binding() returned user_id without legacy flag")
    else:
        report.add(
            "legacy_json_bindings_runtime",
            "pass",
            "get_binding() returns None; legacy JSON disabled by default",
        )


def validate_integrity(report: ValidationReport) -> None:
    counts = _run_integrity_counts()
    report.integrity_counts = counts
    if counts.get("exit_code", 1) != 0:
        report.add("integrity_script", "fail", f"exit_code={counts.get('exit_code')}")
        return
    report.add("integrity_script", "pass", "ops007_telegram_integrity_counts.py completed")

    dup = counts.get("C5_duplicate_telegram_id")
    if isinstance(dup, int) and dup > 0:
        report.add("integrity_duplicate_telegram_id", "fail", f"count={dup}")
    elif isinstance(dup, int):
        report.add("integrity_duplicate_telegram_id", "pass", "0 duplicates")

    svc = counts.get("C6_service_account_with_telegram")
    if isinstance(svc, int) and svc > 0:
        report.add("integrity_service_account_telegram", "warn", f"count={svc}")
    elif isinstance(svc, int):
        report.add("integrity_service_account_telegram", "pass", "0 service accounts with telegram")

    drift = counts.get("C8_tg_bindings_drift")
    if isinstance(drift, int) and drift > 0:
        report.add("integrity_tg_bindings_drift", "warn", f"legacy drift count={drift}")
    elif isinstance(drift, int):
        report.add("integrity_tg_bindings_drift", "pass", "0 legacy tg_bindings drift")


def validate_systemd(report: ValidationReport, units: list[str]) -> None:
    for unit in units:
        status = _systemd_status(unit)
        report.systemd[unit] = status
        active = status.get("ActiveState") == "active"
        if active:
            report.add(f"systemd:{unit}", "pass", f"ActiveState=active MainPID={status.get('MainPID')}")
        else:
            report.add(
                f"systemd:{unit}",
                "fail",
                f"ActiveState={status.get('ActiveState')} Result={status.get('Result')}",
            )

        journal = _journal_recent(unit)
        report.journal_tail[unit] = journal[-4000:] if journal else ""
        exc_lines = _startup_exception_scan(journal)
        if exc_lines:
            report.add(
                f"journal_exceptions:{unit}",
                "warn" if active else "fail",
                "; ".join(exc_lines[-3:]),
            )
        else:
            report.add(f"journal_exceptions:{unit}", "pass", "no Traceback/ERROR in recent journal tail")


def validate_source_of_truth(report: ValidationReport) -> None:
    """Confirm bot client targets internal API paths (code inspection on VPS checkout)."""
    api_path = ROOT / "corpsite-bot" / "src" / "bot" / "integrations" / "corpsite_api.py"
    text = api_path.read_text(encoding="utf-8")
    if "/internal/bot/tg/resolve" in text and "/internal/bot/tasks" in text:
        report.add("bot_client_internal_api", "pass", "corpsite_api.py uses /internal/bot/* paths")
    else:
        report.add("bot_client_internal_api", "fail", "corpsite_api.py missing internal bot paths")

    router_path = ROOT / "app" / "tg_bot_internal_router.py"
    if router_path.is_file():
        report.add("backend_internal_router", "pass", "app/tg_bot_internal_router.py present")
    else:
        report.add("backend_internal_router", "fail", "app/tg_bot_internal_router.py missing")


def run_validation(
    *,
    api_base: str,
    skip_db: bool,
    skip_systemd: bool,
    systemd_units: list[str],
) -> ValidationReport:
    mode = "remote-only" if skip_db and skip_systemd else "vps-full"
    report = ValidationReport(mode=mode, api_base=api_base)

    validate_routes(report, api_base)
    validate_legacy_json(report)
    validate_source_of_truth(report)

    if not skip_db:
        validate_integrity(report)
    else:
        report.add("integrity_script", "skip", "--skip-db")

    if not skip_systemd:
        validate_systemd(report, systemd_units)
    else:
        report.add("systemd", "skip", "--skip-systemd")

    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="OPS-007b read-only Telegram VPS validation")
    parser.add_argument(
        "--api-base",
        default=os.getenv("OPS007B_API_BASE", "http://127.0.0.1:8000"),
        help="Backend API base (default: http://127.0.0.1:8000 or OPS007B_API_BASE)",
    )
    parser.add_argument("--skip-db", action="store_true", help="Skip integrity SQL counts")
    parser.add_argument("--skip-systemd", action="store_true", help="Skip systemd/journal checks")
    parser.add_argument(
        "--systemd-units",
        default="corpsite-backend,corpsite-bot",
        help="Comma-separated systemd units",
    )
    parser.add_argument("--json-out", type=Path, default=None, help="Write JSON report to file")
    args = parser.parse_args()

    units = [u.strip() for u in args.systemd_units.split(",") if u.strip()]
    report = run_validation(
        api_base=args.api_base,
        skip_db=args.skip_db,
        skip_systemd=args.skip_systemd,
        systemd_units=units,
    )

    payload = {
        "mode": report.mode,
        "api_base": report.api_base,
        "overall": "PASS" if report.passed() else "FAIL",
        "checks": [asdict(c) for c in report.checks],
        "integrity_counts": report.integrity_counts,
        "systemd": report.systemd,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.json_out:
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if report.passed() else 1


if __name__ == "__main__":
    raise SystemExit(main())
