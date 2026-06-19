#!/usr/bin/env python3
"""Audit CATEGORY_ROW rows that carry a valid 12-digit IIN (ADR-039 FIO misclassification).

Usage:
  python scripts/audit_hr_category_row_valid_iin.py
  python scripts/audit_hr_category_row_valid_iin.py --batch-id 4
  python scripts/audit_hr_category_row_valid_iin.py --limit 50 --json
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

from app.db.engine import engine
from scripts.import_hr_control_list import infer_row_type

VALID_IIN_SQL = r"""
    length(regexp_replace(COALESCE(r.normalized_payload->>'iin', ''), '[^0-9]', '', 'g')) = 12
"""


def _fetch_category_row_valid_iin(
    conn,
    *,
    batch_id: int | None,
    limit: int,
) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    batch_filter = ""
    params: dict[str, Any] = {"limit": limit}
    if batch_id is not None:
        batch_filter = "AND r.batch_id = :batch_id"
        params["batch_id"] = batch_id

    total = int(
        conn.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM public.hr_import_rows r
                WHERE COALESCE(r.normalized_payload->'metadata'->>'row_type', '') = 'CATEGORY_ROW'
                  AND {VALID_IIN_SQL}
                {batch_filter}
                """
            ),
            params,
        ).scalar_one()
    )

    distribution = [
        dict(row)
        for row in conn.execute(
            text(
                f"""
                SELECT r.batch_id, COUNT(*) AS row_count
                FROM public.hr_import_rows r
                WHERE COALESCE(r.normalized_payload->'metadata'->>'row_type', '') = 'CATEGORY_ROW'
                  AND {VALID_IIN_SQL}
                {batch_filter}
                GROUP BY r.batch_id
                ORDER BY row_count DESC, r.batch_id
                """
            ),
            params,
        ).mappings().all()
    ]

    items = [
        dict(row)
        for row in conn.execute(
            text(
                f"""
                SELECT
                    r.row_id,
                    r.batch_id,
                    r.normalized_payload->>'full_name' AS full_name,
                    regexp_replace(
                        COALESCE(r.normalized_payload->>'iin', ''),
                        '[^0-9]', '', 'g'
                    ) AS iin_digits,
                    r.normalized_payload->'metadata'->>'sheet_type' AS sheet_type,
                    r.normalized_payload->'metadata'->>'classification' AS classification,
                    r.employee_id
                FROM public.hr_import_rows r
                WHERE COALESCE(r.normalized_payload->'metadata'->>'row_type', '') = 'CATEGORY_ROW'
                  AND {VALID_IIN_SQL}
                {batch_filter}
                ORDER BY r.batch_id, r.row_id
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
    ]

    for item in items:
        row_type, is_roster = infer_row_type(
            full_name=str(item.get("full_name") or ""),
            sheet_type=str(item.get("sheet_type") or "doctors"),
            iin_digits=str(item.get("iin_digits") or ""),
        )
        item["would_reclassify_to"] = row_type
        item["would_be_employee_roster"] = is_roster

    return total, distribution, items


def build_audit_report(
    *,
    batch_id: int | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    with engine.connect() as conn:
        total, distribution, items = _fetch_category_row_valid_iin(
            conn,
            batch_id=batch_id,
            limit=limit,
        )

    would_employee = sum(1 for item in items if item.get("would_reclassify_to") == "EMPLOYEE")
    return {
        "filter_batch_id": batch_id,
        "total_category_row_with_valid_iin": total,
        "sample_limit": limit,
        "sample_count": len(items),
        "sample_would_reclassify_to_employee": would_employee,
        "distribution_by_batch_id": distribution,
        "sample_items": items,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Audit CATEGORY_ROW rows with valid IIN (ADR-039 FIO misclassification)"
    )
    parser.add_argument("--batch-id", type=int, default=None)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args()

    report = build_audit_report(batch_id=args.batch_id, limit=args.limit)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0

    print("=== CATEGORY_ROW + valid IIN audit (ADR-039) ===")
    if args.batch_id is not None:
        print(f"batch_id filter: {args.batch_id}")
    print(f"total rows: {report['total_category_row_with_valid_iin']}")
    print(f"sample shown: {report['sample_count']} (limit={args.limit})")
    print(f"sample would reclassify to EMPLOYEE: {report['sample_would_reclassify_to_employee']}")

    print("\n--- distribution by batch_id ---")
    for row in report["distribution_by_batch_id"]:
        print(f"  batch_id={row['batch_id']}: {row['row_count']}")

    print("\n--- first sample rows ---")
    for item in report["sample_items"]:
        print(
            f"  row_id={item['row_id']} batch_id={item['batch_id']} "
            f"iin={item['iin_digits']} "
            f"would->{item['would_reclassify_to']} "
            f"full_name={item['full_name']!r}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
