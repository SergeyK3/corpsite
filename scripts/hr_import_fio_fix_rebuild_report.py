#!/usr/bin/env python3
"""Reclassify mis-typed HR import rows and rebuild normalized records (ADR-039).

Captures before/after metrics for roster rows, normalized records, and canonical
snapshot entries. Optionally applies row_type reclassification and repopulates
staging normalized records.

Usage:
  python scripts/hr_import_fio_fix_rebuild_report.py --batch-id 4 --dry-run
  python scripts/hr_import_fio_fix_rebuild_report.py --batch-id 4 --apply
  # VPS production orchestration (ADR-039 + ADR-040):
  python scripts/adr040_vps_production_flow.py inspect
  python scripts/adr040_vps_production_flow.py run-all --batch-id 4 --promoted-by 1 --execute
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.db.models.hr_import import (
    CLASSIFICATION_CATEGORY_ROW,
    CLASSIFICATION_DECLARATION,
    CLASSIFICATION_DUPLICATE_IIN,
    CLASSIFICATION_INVALID_IIN,
    CLASSIFICATION_NORMAL,
    CLASSIFICATION_PART_TIME,
    CLASSIFICATION_SUMMARY_ROW,
    ROW_TYPE_CATEGORY_ROW,
    ROW_TYPE_DECLARATION_PERSON,
    ROW_TYPE_DECLARATION_ROW,
    ROW_TYPE_SUMMARY_ROW,
)
from app.services.hr_import_normalized_record_service import (
    normalized_records_available,
    populate_normalized_records,
)
from scripts.diagnose_hr_import_batch_bindings import _table_column_names
from scripts.import_hr_control_list import ParsedRow, clean_iin, infer_row_type

VALID_IIN_SQL = r"""
    length(regexp_replace(COALESCE(normalized_payload->>'iin', ''), '[^0-9]', '', 'g')) = 12
"""


def _snapshot_batch_join_filter(conn: Connection, batch_id: int) -> tuple[str, dict[str, Any]]:
    columns = _table_column_names(conn, "hr_canonical_snapshots")
    if "source_batch_id" in columns:
        return "s.source_batch_id = :batch_id", {"batch_id": batch_id}
    if "batch_id" in columns:
        return "s.batch_id = :batch_id", {"batch_id": batch_id}
    return "FALSE", {}


def _table_exists(conn: Connection, table_name: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table_name
                """
            ),
            {"table_name": table_name},
        ).first()
    )


def _batch_metrics(conn: Connection, batch_id: int) -> dict[str, int]:
    roster_rows = int(
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
    )
    category_valid_iin = int(
        conn.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                  AND COALESCE(normalized_payload->'metadata'->>'row_type', '') = 'CATEGORY_ROW'
                  AND {VALID_IIN_SQL}
                """
            ),
            {"batch_id": batch_id},
        ).scalar_one()
    )
    normalized_rows = 0
    if _table_exists(conn, "hr_import_normalized_records"):
        normalized_rows = int(
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
        )
    snapshot_entries = 0
    if _table_exists(conn, "hr_canonical_snapshot_entries") and _table_exists(
        conn, "hr_canonical_snapshots"
    ):
        batch_filter, batch_params = _snapshot_batch_join_filter(conn, batch_id)
        snapshot_entries = int(
            conn.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM public.hr_canonical_snapshot_entries e
                    JOIN public.hr_canonical_snapshots s ON s.snapshot_id = e.snapshot_id
                    WHERE {batch_filter}
                    """
                ),
                batch_params,
            ).scalar_one()
        )
    return {
        "roster_employee_rows": roster_rows,
        "category_row_with_valid_iin": category_valid_iin,
        "normalized_records": normalized_rows,
        "canonical_snapshot_entries": snapshot_entries,
    }


def _classify_row(row: ParsedRow, duplicate_iins: set[str]) -> str:
    if row.row_type in (ROW_TYPE_DECLARATION_PERSON, ROW_TYPE_DECLARATION_ROW):
        return CLASSIFICATION_DECLARATION
    if row.row_type == ROW_TYPE_CATEGORY_ROW:
        return CLASSIFICATION_CATEGORY_ROW
    if row.row_type == ROW_TYPE_SUMMARY_ROW:
        return CLASSIFICATION_SUMMARY_ROW
    if row.sheet_type == "part_time":
        return CLASSIFICATION_PART_TIME
    if not row.is_employee_roster:
        return CLASSIFICATION_SUMMARY_ROW
    if row.iin_digits and not row.iin_valid:
        return CLASSIFICATION_INVALID_IIN
    if row.iin_digits in duplicate_iins:
        return CLASSIFICATION_DUPLICATE_IIN
    return CLASSIFICATION_NORMAL


def _load_batch_rows(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            text(
                """
                SELECT row_id, normalized_payload
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                ORDER BY row_id
                """
            ),
            {"batch_id": batch_id},
        ).mappings().all()
    ]


def _reclassify_batch(conn: Connection, batch_id: int, *, dry_run: bool) -> dict[str, Any]:
    db_rows = _load_batch_rows(conn, batch_id)
    planned: list[dict[str, Any]] = []
    parsed_by_row_id: dict[int, ParsedRow] = {}

    for db_row in db_rows:
        row_id = int(db_row["row_id"])
        payload = dict(db_row["normalized_payload"] or {})
        metadata = dict(payload.get("metadata") or {})
        full_name = str(payload.get("full_name") or "")
        sheet_type = str(metadata.get("sheet_type") or "")
        iin_digits = str(payload.get("iin") or "")
        _, iin_valid, _ = clean_iin(iin_digits)

        new_row_type, new_is_roster = infer_row_type(
            full_name=full_name,
            sheet_type=sheet_type,
            iin_digits=iin_digits,
        )
        old_row_type = str(metadata.get("row_type") or "")
        old_is_roster = bool(metadata.get("is_employee_roster", False))

        parsed = ParsedRow(
            data={key: str(payload.get(key, "") or "") for key in payload if key != "metadata"},
            sheet_type=sheet_type,
            row_type=new_row_type,
            declaration_group=str(metadata.get("declaration_group") or ""),
            is_employee_roster=new_is_roster,
            iin_valid=iin_valid,
            iin_digits=iin_digits,
            errors=[],
        )
        parsed_by_row_id[row_id] = parsed

        if old_row_type == new_row_type and old_is_roster == new_is_roster:
            continue

        planned.append(
            {
                "row_id": row_id,
                "full_name": full_name,
                "iin_digits": iin_digits,
                "old_row_type": old_row_type,
                "new_row_type": new_row_type,
                "old_is_employee_roster": old_is_roster,
                "new_is_employee_roster": new_is_roster,
            }
        )

    duplicate_iins = {
        row.iin_digits
        for row in parsed_by_row_id.values()
        if row.iin_digits
        and row.is_employee_roster
        and sum(
            1
            for other in parsed_by_row_id.values()
            if other.iin_digits == row.iin_digits and other.is_employee_roster
        )
        > 1
    }

    updated = 0
    if not dry_run:
        for item in planned:
            db_row = next(row for row in db_rows if int(row["row_id"]) == item["row_id"])
            payload = dict(db_row["normalized_payload"] or {})
            metadata = dict(payload.get("metadata") or {})
            parsed = parsed_by_row_id[item["row_id"]]
            metadata["row_type"] = item["new_row_type"]
            metadata["is_employee_roster"] = item["new_is_employee_roster"]
            metadata["classification"] = _classify_row(parsed, duplicate_iins)
            payload["metadata"] = metadata
            conn.execute(
                text(
                    """
                    UPDATE public.hr_import_rows
                    SET normalized_payload = CAST(:normalized_payload AS jsonb)
                    WHERE row_id = :row_id
                    """
                ),
                {
                    "row_id": item["row_id"],
                    "normalized_payload": json.dumps(payload, ensure_ascii=False),
                },
            )
            updated += 1

    transitions = Counter(
        f"{item['old_row_type']}->{item['new_row_type']}" for item in planned
    )
    return {
        "batch_id": batch_id,
        "rows_scanned": len(db_rows),
        "rows_to_update": len(planned),
        "rows_updated": updated,
        "transitions": dict(transitions),
        "sample_updates": planned[:20],
    }


def _snapshot_impact(conn: Connection, batch_id: int) -> dict[str, Any]:
    rows = conn.execute(
        text(
            f"""
            SELECT
                r.row_id,
                r.normalized_payload->>'full_name' AS full_name,
                regexp_replace(
                    COALESCE(r.normalized_payload->>'iin', ''),
                    '[^0-9]', '', 'g'
                ) AS iin_digits,
                r.normalized_payload->'metadata'->>'sheet_type' AS sheet_type,
                r.normalized_payload->'metadata'->>'row_type' AS row_type
            FROM public.hr_import_rows r
            WHERE r.batch_id = :batch_id
              AND COALESCE(r.normalized_payload->'metadata'->>'row_type', '') = 'CATEGORY_ROW'
              AND {VALID_IIN_SQL}
            ORDER BY r.row_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()

    missing_from_snapshot: list[dict[str, Any]] = []
    for row in rows:
        full_name = str(row.get("full_name") or "")
        sheet_type = str(row.get("sheet_type") or "doctors")
        iin_digits = str(row.get("iin_digits") or "")
        new_row_type, _ = infer_row_type(
            full_name=full_name,
            sheet_type=sheet_type,
            iin_digits=iin_digits,
        )
        if new_row_type != "EMPLOYEE":
            continue

        in_snapshot = False
        if _table_exists(conn, "hr_canonical_snapshot_entries"):
            batch_filter, batch_params = _snapshot_batch_join_filter(conn, batch_id)
            found = conn.execute(
                text(
                    f"""
                    SELECT 1
                    FROM public.hr_canonical_snapshot_entries e
                    JOIN public.hr_canonical_snapshots s ON s.snapshot_id = e.snapshot_id
                    WHERE {batch_filter}
                      AND e.source_row_id = :row_id
                    LIMIT 1
                    """
                ),
                {**batch_params, "row_id": int(row["row_id"])},
            ).first()
            in_snapshot = found is not None

        if not in_snapshot:
            missing_from_snapshot.append(
                {
                    "row_id": int(row["row_id"]),
                    "full_name": full_name,
                    "iin_digits": iin_digits,
                    "current_row_type": str(row.get("row_type") or ""),
                    "would_reclassify_to": new_row_type,
                }
            )

    return {
        "batch_id": batch_id,
        "misclassified_category_row_with_valid_iin": len(rows),
        "would_become_employee": sum(
            1
            for row in rows
            if infer_row_type(
                full_name=str(row.get("full_name") or ""),
                sheet_type=str(row.get("sheet_type") or "doctors"),
                iin_digits=str(row.get("iin_digits") or ""),
            )[0]
            == "EMPLOYEE"
        ),
        "missing_from_canonical_snapshot_due_to_misclassification": len(missing_from_snapshot),
        "sample_missing": missing_from_snapshot[:50],
    }


def process_batch(conn: Connection, batch_id: int, *, apply: bool) -> dict[str, Any]:
    before = _batch_metrics(conn, batch_id)
    reclassify = _reclassify_batch(conn, batch_id, dry_run=not apply)
    populate_summary = None
    populate_error = None
    if apply:
        conn.commit()
        after_reclassify = _batch_metrics(conn, batch_id)
        if normalized_records_available(conn):
            try:
                populate_summary = populate_normalized_records(conn, batch_id)
                conn.commit()
            except Exception as exc:
                conn.rollback()
                populate_error = str(exc)
        after = _batch_metrics(conn, batch_id)
    else:
        after_reclassify = before
        after = before

    delta = {key: after[key] - before[key] for key in before}
    delta_reclassify = {key: after_reclassify[key] - before[key] for key in before}
    return {
        "batch_id": batch_id,
        "dry_run": not apply,
        "before": before,
        "after_reclassify": after_reclassify,
        "after": after,
        "delta_reclassify": delta_reclassify,
        "delta": delta,
        "reclassify": reclassify,
        "populate_normalized_records": populate_summary,
        "populate_error": populate_error,
        "snapshot_impact": _snapshot_impact(conn, batch_id),
    }


def build_report(*, batch_ids: list[int], apply: bool) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    with engine.connect() as conn:
        for batch_id in batch_ids:
            reports.append(process_batch(conn, batch_id, apply=apply))
    return {"batches": reports, "apply": apply}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="ADR-039 FIO fix rebuild and impact report")
    parser.add_argument("--batch-id", type=int, action="append", dest="batch_ids", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist reclassification and repopulate normalized records",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report(batch_ids=args.batch_ids, apply=args.apply)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0

    print("=== ADR-039 FIO fix rebuild report ===")
    print(f"mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    for batch in report["batches"]:
        print(f"\n--- batch_id={batch['batch_id']} ---")
        print(f"before: {batch['before']}")
        print(f"after_reclassify: {batch['after_reclassify']}")
        print(f"after:  {batch['after']}")
        print(f"delta_reclassify: {batch['delta_reclassify']}")
        print(f"delta:  {batch['delta']}")
        if batch.get("populate_error"):
            print(f"populate_error: {batch['populate_error']}")
        print(
            "reclassify: "
            f"{batch['reclassify']['rows_to_update']} rows to update "
            f"({batch['reclassify']['transitions']})"
        )
        impact = batch["snapshot_impact"]
        print(
            "snapshot impact: "
            f"{impact['missing_from_canonical_snapshot_due_to_misclassification']} "
            "employees missing from canonical snapshot due to misclassification"
        )
        for item in impact.get("sample_missing", [])[:5]:
            print(
                f"  row_id={item['row_id']} iin={item['iin_digits']} "
                f"full_name={item['full_name']!r}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
