#!/usr/bin/env python3
"""One-shot backfill: hr_import_normalized_records from existing import batches (ADR-039 3C).

Safe for production:
- calls populate_normalized_records() only (staging layer)
- does not write employee_documents
- does not run promotion
- idempotent per batch (rebuilds pending/rejected/superseded staging rows)

Examples:
  python scripts/backfill_hr_import_normalized_records.py --all
  python scripts/backfill_hr_import_normalized_records.py --latest
  python scripts/backfill_hr_import_normalized_records.py --batch-id 4
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
from app.services.hr_import_analytics_service import list_batches
from app.services.hr_import_normalized_record_service import (
    normalized_records_available,
    populate_normalized_records,
)


def _load_batch_ids(conn, latest_only: bool) -> list[int]:
    data = list_batches(conn)
    ids = [int(item["batch_id"]) for item in data["items"]]
    if latest_only:
        return ids[:1]
    return ids


def _staging_count(conn) -> int:
    return int(
        conn.execute(text("SELECT COUNT(*) FROM public.hr_import_normalized_records")).scalar_one()
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill hr_import_normalized_records from existing HR import batches"
    )
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--all", action="store_true", help="Process every hr_import_batches row")
    scope.add_argument("--latest", action="store_true", help="Process only the most recent batch")
    scope.add_argument("--batch-id", type=int, dest="batch_id", help="Process a single batch_id")
    args = parser.parse_args()

    with engine.connect() as conn:
        if not normalized_records_available(conn):
            print(
                "ERROR: table hr_import_normalized_records is missing. "
                "Run alembic upgrade head (ADR-039 Phase 3B) first.",
                file=sys.stderr,
            )
            return 1

        if args.batch_id is not None:
            batch_ids = [args.batch_id]
        else:
            batch_ids = _load_batch_ids(conn, latest_only=args.latest)
        before_total = _staging_count(conn)

    if not batch_ids:
        print("No import batches found in hr_import_batches.")
        return 0

    results: list[dict] = []

    for batch_id in batch_ids:
        with engine.begin() as conn:
            summary = populate_normalized_records(conn, batch_id)
        results.append(summary)
        print(json.dumps(summary, ensure_ascii=False))

    with engine.connect() as conn:
        after_total = _staging_count(conn)

    print(
        json.dumps(
            {
                "batches_processed": len(batch_ids),
                "batch_ids": batch_ids,
                "staging_count_before": before_total,
                "staging_count_after": after_total,
                "employee_documents": "not_modified",
                "promotion": "not_run",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
