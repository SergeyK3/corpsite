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
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine

BATCH_TABLE = "hr_import_batches"
FILENAME_COLUMN_CANDIDATES = ("file_name", "source_filename")


def _table_column_names(conn: Connection, table_name: str, *, schema: str = "public") -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table_name
            """
        ),
        {"schema": schema, "table_name": table_name},
    ).scalars().all()
    return {str(name) for name in rows}


def batch_filename_sql_expr(available_columns: Iterable[str]) -> str:
    """Return SQL expression for batch filename across schema variants."""
    cols = set(available_columns)
    present = [name for name in FILENAME_COLUMN_CANDIDATES if name in cols]
    if not present:
        return "NULL"
    if len(present) == 1:
        return present[0]
    return f"COALESCE({', '.join(present)})"


def batch_header_select_sql(available_columns: Iterable[str]) -> str:
    """Build SELECT for hr_import_batches header fields."""
    cols = set(available_columns)
    required = {"batch_id", "imported_at", "status"}
    missing = sorted(required - cols)
    if missing:
        raise ValueError(f"hr_import_batches missing required columns: {', '.join(missing)}")

    filename_expr = batch_filename_sql_expr(cols)
    return f"""
        SELECT
            batch_id,
            {filename_expr} AS file_name,
            imported_at,
            status
        FROM public.hr_import_batches
        WHERE batch_id = :batch_id
    """


def fetch_batch_header(conn: Connection, batch_id: int) -> dict | None:
    columns = _table_column_names(conn, BATCH_TABLE)
    sql = batch_header_select_sql(columns)
    row = conn.execute(text(sql), {"batch_id": batch_id}).mappings().first()
    return dict(row) if row is not None else None


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
        batch = fetch_batch_header(conn, batch_id)
        if batch is None:
            print(f"Batch {batch_id} not found")
            return
        print(json.dumps(batch, default=str, indent=2))

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
