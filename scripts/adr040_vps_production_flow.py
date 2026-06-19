#!/usr/bin/env python3
"""ADR-039/040 — production-safe VPS flow (batch 4 → canonical snapshot v2).

Designed for VPS where:
  - active snapshot v1 = batch 39
  - latest unpromoted import = batch 4
  - hr_change_events = 0 until promotion

Safe defaults: all mutating subcommands require --execute (otherwise dry-run).

Typical VPS session (from /opt/projects/corpsite/app):

  # 0) Deploy code with Kazakh FIO fix + uq_hinr supersede fix, then:
  .venv/bin/python3 scripts/adr040_vps_production_flow.py inspect

  # 1) Dry-run full pipeline
  .venv/bin/python3 scripts/adr040_vps_production_flow.py run-all --batch-id 4

  # 2) Apply step-by-step (recommended)
  .venv/bin/python3 scripts/adr040_vps_production_flow.py fio-fix --batch-id 4 --execute
  .venv/bin/python3 scripts/adr040_vps_production_flow.py promote --batch-id 4 --promoted-by 1 --execute
  .venv/bin/python3 scripts/adr040_vps_production_flow.py verify --batch-id 4

  # Or one-shot after review:
  .venv/bin/python3 scripts/adr040_vps_production_flow.py run-all --batch-id 4 --promoted-by 1 --execute
"""
from __future__ import annotations

import argparse
import json
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openpyxl import load_workbook
from sqlalchemy import text

from app.db.engine import engine
from app.services.hr_canonical_snapshot_service import SNAPSHOT_STATUS_ACTIVE
from app.services.hr_change_events_export_service import export_hr_change_events_xlsx
from app.services.hr_import_monthly_diff_service import compute_batch_monthly_diff
from app.services.hr_snapshot_comparison_service import list_hr_change_events
from scripts.adr040_production_phase_h_verify import (
    inspect_state,
    promote_batch,
    verify_events,
    verify_export,
)
from scripts.audit_hr_category_row_valid_iin import build_audit_report
from scripts.hr_import_fio_fix_rebuild_report import build_report as build_fio_fix_report
from scripts.import_hr_control_list import infer_row_type, looks_like_person_name

DEFAULT_BATCH_ID = 4
DEFAULT_PRIOR_BATCH_ID = 39
ABITAEV_IIN = "800115300290"
ABITAEV_FIO = "Әбитаев Ерхан Сайлаубекұлы"


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _resolve_promoted_by(conn, explicit: Optional[int]) -> int:
    if explicit is not None:
        return int(explicit)
    row = conn.execute(
        text("SELECT user_id FROM public.users ORDER BY user_id LIMIT 1")
    ).scalar_one_or_none()
    if row is None:
        raise RuntimeError("No users in database — pass --promoted-by")
    return int(row)


def _active_snapshot(conn) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT snapshot_id, source_batch_id, version, status, entry_count, promoted_at
            FROM public.hr_canonical_snapshots
            WHERE status = :status
            ORDER BY version DESC
            LIMIT 1
            """
        ),
        {"status": SNAPSHOT_STATUS_ACTIVE},
    ).mappings().first()
    return dict(row) if row else None


def _batch_exists(conn, batch_id: int) -> bool:
    return bool(
        conn.execute(
            text("SELECT 1 FROM public.hr_import_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        ).first()
    )


def preflight_code_fix() -> dict[str, Any]:
    row_type, is_roster = infer_row_type(
        full_name=ABITAEV_FIO,
        sheet_type="doctors",
        iin_digits=ABITAEV_IIN,
    )
    return {
        "kazakh_fio_fix_loaded": row_type == "EMPLOYEE" and is_roster is True,
        "looks_like_person_name": looks_like_person_name(ABITAEV_FIO),
        "infer_row_type": {"row_type": row_type, "is_employee_roster": is_roster},
        "sample_fio": ABITAEV_FIO,
        "sample_iin": ABITAEV_IIN,
    }


def cmd_inspect(*, batch_id: int) -> dict[str, Any]:
    state = inspect_state()
    with engine.connect() as conn:
        active = _active_snapshot(conn)
        batch_exists = _batch_exists(conn, batch_id)
        metrics = {}
        if batch_exists:
            metrics = {
                "hr_import_rows": int(
                    conn.execute(
                        text(
                            "SELECT COUNT(*) FROM public.hr_import_rows WHERE batch_id = :batch_id"
                        ),
                        {"batch_id": batch_id},
                    ).scalar_one()
                ),
                "roster_employee_rows": int(
                    conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM public.hr_import_rows
                            WHERE batch_id = :batch_id
                              AND COALESCE(normalized_payload->'metadata'->>'row_type', '') = 'EMPLOYEE'
                            """
                        ),
                        {"batch_id": batch_id},
                    ).scalar_one()
                ),
                "normalized_records": int(
                    conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM public.hr_import_normalized_records
                            WHERE batch_id = :batch_id
                            """
                        ),
                        {"batch_id": batch_id},
                    ).scalar_one()
                ),
            }
            diff_rows = conn.execute(
                text(
                    """
                    SELECT COALESCE(diff_status, 'NULL') AS diff_status, COUNT(*) AS cnt
                    FROM public.hr_import_rows
                    WHERE batch_id = :batch_id
                    GROUP BY diff_status
                    ORDER BY diff_status
                    """
                ),
                {"batch_id": batch_id},
            ).mappings().all()
            metrics["diff_status_counts"] = {str(r["diff_status"]): int(r["cnt"]) for r in diff_rows}

        category_audit = build_audit_report(batch_id=batch_id, limit=20) if batch_exists else None

    return {
        "target_batch_id": batch_id,
        "expected_prior_batch_id": DEFAULT_PRIOR_BATCH_ID,
        "batch_exists": batch_exists,
        "code_preflight": preflight_code_fix(),
        "active_snapshot": active,
        "batch_metrics": metrics,
        "category_row_valid_iin_audit": category_audit,
        "global_state": state,
        "ready_for_fio_fix": batch_exists and preflight_code_fix()["kazakh_fio_fix_loaded"],
        "ready_for_promote": batch_exists and active is not None,
    }


def cmd_fio_fix(*, batch_id: int, execute: bool) -> dict[str, Any]:
    with engine.connect() as conn:
        if not _batch_exists(conn, batch_id):
            raise RuntimeError(f"batch_id={batch_id} not found on this server")
    audit_before = build_audit_report(batch_id=batch_id, limit=100)
    report = build_fio_fix_report(batch_ids=[batch_id], apply=execute)
    audit_after = build_audit_report(batch_id=batch_id, limit=100) if execute else audit_before
    return {
        "batch_id": batch_id,
        "execute": execute,
        "code_preflight": preflight_code_fix(),
        "category_row_valid_iin_before": audit_before["total_category_row_with_valid_iin"],
        "category_row_valid_iin_after": audit_after["total_category_row_with_valid_iin"],
        "fio_fix_report": report,
    }


def cmd_promote(*, batch_id: int, promoted_by: Optional[int], execute: bool) -> dict[str, Any]:
    with engine.connect() as conn:
        if not _batch_exists(conn, batch_id):
            raise RuntimeError(f"batch_id={batch_id} not found on this server")
        active = _active_snapshot(conn)
        promoted_by_id = _resolve_promoted_by(conn, promoted_by) if execute else promoted_by

    if not execute:
        return {
            "dry_run": True,
            "would_promote_batch_id": batch_id,
            "would_promoted_by": promoted_by_id,
            "active_snapshot_before": active,
            "steps": [
                "compute_batch_monthly_diff(batch_id)",
                "build_canonical_snapshot_from_batch(batch_id) → v2",
                "materialize hr_change_events (prior active → new)",
            ],
        }

    with engine.begin() as conn:
        diff_result = compute_batch_monthly_diff(conn, batch_id)

    promotion = promote_batch(batch_id=batch_id, promoted_by=int(promoted_by_id), execute=True)

    with engine.connect() as conn:
        active_after = _active_snapshot(conn)

    return {
        "dry_run": False,
        "batch_id": batch_id,
        "promoted_by": promoted_by_id,
        "active_snapshot_before": active,
        "active_snapshot_after": active_after,
        "monthly_diff": {
            "snapshot_id": diff_result.get("snapshot_id"),
            "summary": diff_result.get("summary"),
            "removed_count": len(diff_result.get("removed") or []),
        },
        "promotion": promotion,
    }


def _track_abitaev(conn, *, batch_id: int, new_snapshot_id: Optional[int]) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT row_id, employee_id, match_status,
                   normalized_payload->'metadata'->>'row_type' AS row_type,
                   normalized_payload->'metadata'->>'is_employee_roster' AS is_employee_roster,
                   normalized_payload->>'full_name' AS full_name,
                   diff_status
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
              AND regexp_replace(COALESCE(normalized_payload->>'iin', ''), '[^0-9]', '', 'g') = :iin
            """
        ),
        {"batch_id": batch_id, "iin": ABITAEV_IIN},
    ).mappings().first()

    norm_count = 0
    if row:
        norm_count = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.hr_import_normalized_records
                    WHERE row_id = :row_id
                    """
                ),
                {"row_id": int(row["row_id"])},
            ).scalar_one()
        )

    snapshot_entries = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT e.entry_id, e.snapshot_id, s.version, s.status, s.source_batch_id,
                       e.employee_id, e.iin, e.match_key
                FROM public.hr_canonical_snapshot_entries e
                JOIN public.hr_canonical_snapshots s ON s.snapshot_id = e.snapshot_id
                WHERE regexp_replace(COALESCE(e.iin, ''), '[^0-9]', '', 'g') = :iin
                ORDER BY s.version
                """
            ),
            {"iin": ABITAEV_IIN},
        ).mappings().all()
    ]

    change_events = []
    if new_snapshot_id is not None:
        change_events = list_hr_change_events(
            conn,
            new_snapshot_id=int(new_snapshot_id),
            limit=500,
        )["items"]
        change_events = [
            item
            for item in change_events
            if ABITAEV_IIN in str(item.get("iin") or "")
            or ABITAEV_IIN.replace("0", "") in str(item.get("iin") or "")
        ]

    return {
        "import_row": dict(row) if row else None,
        "normalized_records_count": norm_count,
        "snapshot_entries": snapshot_entries,
        "hr_change_events_for_iin": change_events,
        "expected_after_success": {
            "row_type": "EMPLOYEE",
            "is_employee_roster": True,
            "normalized_records_count_gt": 0,
            "in_active_snapshot_v2": True,
        },
    }


def cmd_verify(*, batch_id: int, export_path: Optional[Path]) -> dict[str, Any]:
    events = verify_events()
    export = verify_export(output_path=export_path or (ROOT / "tmp" / "vps_hr_registry_changes.xlsx"))

    with engine.connect() as conn:
        active = _active_snapshot(conn)
        new_snapshot_id = int(active["snapshot_id"]) if active else None
        abitaev = _track_abitaev(conn, batch_id=batch_id, new_snapshot_id=new_snapshot_id)

        api_checks = {}
        if new_snapshot_id is not None:
            for et in ("NEW", "REMOVED"):
                api_checks[et] = list_hr_change_events(
                    conn, event_type=et, new_snapshot_id=new_snapshot_id, limit=3
                )["total"]
            api_checks["source_batch"] = list_hr_change_events(
                conn, source_batch_id=batch_id, limit=3
            )["total"]

    return {
        "batch_id": batch_id,
        "active_snapshot": active,
        "verify_events": events,
        "verify_export": export,
        "api_checks": api_checks,
        "abitaev_tracking": abitaev,
        "acceptance": {
            "hr_change_events_gt_0": events.get("total", 0) > 0,
            "export_has_data": export.get("ok", False),
            "active_snapshot_source_batch_is_target": (
                active is not None and int(active.get("source_batch_id") or 0) == batch_id
            ),
            "active_snapshot_version_is_2": (
                active is not None and int(active.get("version") or 0) >= 2
            ),
        },
    }


def cmd_run_all(*, batch_id: int, promoted_by: Optional[int], execute: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "batch_id": batch_id,
        "execute": execute,
        "inspect": cmd_inspect(batch_id=batch_id),
    }
    if not report["inspect"]["batch_exists"]:
        report["aborted"] = f"batch_id={batch_id} not found — stop"
        return report
    if not report["inspect"]["code_preflight"]["kazakh_fio_fix_loaded"]:
        report["aborted"] = "Kazakh FIO fix not in deployed code — deploy first"
        return report

    report["fio_fix"] = cmd_fio_fix(batch_id=batch_id, execute=execute)
    if execute and report["fio_fix"]["fio_fix_report"]["batches"][0].get("populate_error"):
        report["aborted"] = "populate failed — fix before promote"
        report["populate_error"] = report["fio_fix"]["fio_fix_report"]["batches"][0]["populate_error"]
        return report

    report["promote"] = cmd_promote(batch_id=batch_id, promoted_by=promoted_by, execute=execute)
    if execute:
        report["verify"] = cmd_verify(batch_id=batch_id, export_path=None)
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="ADR-039/040 production-safe VPS flow (default batch 4 → snapshot v2)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect", help="Read-only VPS preflight")
    p_inspect.add_argument("--batch-id", type=int, default=DEFAULT_BATCH_ID)

    p_fio = sub.add_parser("fio-fix", help="ADR-039 reclassify + populate normalized records")
    p_fio.add_argument("--batch-id", type=int, default=DEFAULT_BATCH_ID)
    p_fio.add_argument("--execute", action="store_true")

    p_promote = sub.add_parser("promote", help="Monthly diff + canonical snapshot v2 + change events")
    p_promote.add_argument("--batch-id", type=int, default=DEFAULT_BATCH_ID)
    p_promote.add_argument("--promoted-by", type=int, default=None)
    p_promote.add_argument("--execute", action="store_true")

    p_verify = sub.add_parser("verify", help="hr_change_events + Excel export + Әбітаев tracking")
    p_verify.add_argument("--batch-id", type=int, default=DEFAULT_BATCH_ID)
    p_verify.add_argument("--export", type=Path, default=None)

    p_all = sub.add_parser("run-all", help="inspect → fio-fix → promote → verify")
    p_all.add_argument("--batch-id", type=int, default=DEFAULT_BATCH_ID)
    p_all.add_argument("--promoted-by", type=int, default=None)
    p_all.add_argument("--execute", action="store_true")

    args = parser.parse_args()

    if args.command == "inspect":
        _print_json(cmd_inspect(batch_id=args.batch_id))
    elif args.command == "fio-fix":
        _print_json(cmd_fio_fix(batch_id=args.batch_id, execute=args.execute))
    elif args.command == "promote":
        _print_json(cmd_promote(batch_id=args.batch_id, promoted_by=args.promoted_by, execute=args.execute))
    elif args.command == "verify":
        _print_json(cmd_verify(batch_id=args.batch_id, export_path=args.export))
    elif args.command == "run-all":
        _print_json(cmd_run_all(batch_id=args.batch_id, promoted_by=args.promoted_by, execute=args.execute))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
