#!/usr/bin/env python3
"""Diagnose HR import batch binding issues (ADR-039/040).

Usage:
  python scripts/diagnose_hr_import_batch_bindings.py --batch-id 4 --iin 800115300290
  python scripts/diagnose_hr_import_batch_bindings.py --batch-id 4 --employee-id 24
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.engine import engine


def _print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(row) for row in rows]


def diagnose_batch(
    *,
    batch_id: int,
    iin: str | None = None,
    employee_id: int | None = None,
) -> None:
    iin_digits = "".join(ch for ch in (iin or "") if ch.isdigit())

    with engine.connect() as conn:
        batch = conn.execute(
            text(
                """
                SELECT batch_id, source_filename, imported_at, status
                FROM public.hr_import_batches
                WHERE batch_id = :batch_id
                """
            ),
            {"batch_id": batch_id},
        ).mappings().first()
        if batch is None:
            print(f"Batch {batch_id} not found")
            return
        print(json.dumps(dict(batch), default=str, indent=2))

        if iin_digits:
            _print_section(f"Normalized records by IIN {iin_digits}")
            rows = conn.execute(
                text(
                    """
                    SELECT
                        nr.normalized_record_id,
                        nr.row_id,
                        nr.employee_id,
                        nr.record_kind,
                        nr.document_type_code,
                        nr.source_record_key,
                        nr.review_status,
                        r.normalized_payload->>'full_name' AS full_name,
                        r.normalized_payload->>'iin' AS iin
                    FROM public.hr_import_normalized_records nr
                    JOIN public.hr_import_rows r ON r.row_id = nr.row_id
                    WHERE nr.batch_id = :batch_id
                      AND regexp_replace(COALESCE(r.normalized_payload->>'iin', ''), '[^0-9]', '', 'g')
                          LIKE :iin_pattern
                    ORDER BY nr.normalized_record_id
                    """
                ),
                {"batch_id": batch_id, "iin_pattern": f"%{iin_digits}%"},
            ).mappings().all()
            print(json.dumps(_rows_to_dicts(rows), default=str, indent=2))
            print(f"count: {len(rows)}")

        if employee_id is not None:
            _print_section(f"Records with employee_id={employee_id}")
            rows = conn.execute(
                text(
                    """
                    SELECT
                        nr.normalized_record_id,
                        nr.row_id,
                        nr.record_kind,
                        nr.document_type_code,
                        nr.source_record_key,
                        nr.review_status,
                        r.normalized_payload->>'full_name' AS full_name,
                        r.normalized_payload->>'iin' AS iin
                    FROM public.hr_import_normalized_records nr
                    JOIN public.hr_import_rows r ON r.row_id = nr.row_id
                    WHERE nr.batch_id = :batch_id AND nr.employee_id = :employee_id
                    ORDER BY nr.normalized_record_id
                    """
                ),
                {"batch_id": batch_id, "employee_id": employee_id},
            ).mappings().all()
            print(json.dumps(_rows_to_dicts(rows), default=str, indent=2))
            print(f"count: {len(rows)}")

        _print_section(f"Duplicate source_record_key groups (open, batch {batch_id})")
        rows = conn.execute(
            text(
                """
                SELECT
                    employee_id,
                    source_record_key,
                    COUNT(*) AS cnt,
                    array_agg(normalized_record_id ORDER BY normalized_record_id) AS record_ids,
                    array_agg(record_kind ORDER BY normalized_record_id) AS record_kinds,
                    array_agg(review_status ORDER BY normalized_record_id) AS review_statuses
                FROM public.hr_import_normalized_records
                WHERE batch_id = :batch_id
                  AND employee_id IS NOT NULL
                  AND promoted_document_id IS NULL
                  AND review_status IN ('pending', 'approved')
                GROUP BY employee_id, source_record_key
                HAVING COUNT(*) > 1
                ORDER BY cnt DESC, employee_id, source_record_key
                """
            ),
            {"batch_id": batch_id},
        ).mappings().all()
        print(json.dumps(_rows_to_dicts(rows), default=str, indent=2))
        print(f"duplicate groups: {len(rows)}")

        _print_section(f"Same source_record_key across different record_id/kind (batch {batch_id})")
        rows = conn.execute(
            text(
                """
                SELECT
                    source_record_key,
                    COUNT(DISTINCT normalized_record_id) AS record_count,
                    COUNT(DISTINCT record_kind) AS kind_count,
                    array_agg(DISTINCT normalized_record_id ORDER BY normalized_record_id) AS record_ids,
                    array_agg(DISTINCT record_kind ORDER BY record_kind) AS record_kinds
                FROM public.hr_import_normalized_records
                WHERE batch_id = :batch_id
                  AND source_record_key IS NOT NULL
                  AND source_record_key <> ''
                GROUP BY source_record_key
                HAVING COUNT(DISTINCT normalized_record_id) > 1
                ORDER BY record_count DESC
                LIMIT 50
                """
            ),
            {"batch_id": batch_id},
        ).mappings().all()
        print(json.dumps(_rows_to_dicts(rows), default=str, indent=2))
        print(f"key collision groups: {len(rows)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose HR import batch binding duplicates")
    parser.add_argument("--batch-id", type=int, required=True)
    parser.add_argument("--iin", type=str, default=None)
    parser.add_argument("--employee-id", type=int, default=None)
    args = parser.parse_args()
    diagnose_batch(batch_id=args.batch_id, iin=args.iin, employee_id=args.employee_id)


if __name__ == "__main__":
    main()
