#!/usr/bin/env python3
"""Repair employee bindings for HR import batches (ADR-039 Phase 3G).

Auto-binds import rows by IIN (primary) or normalized FIO (fallback), then
propagates employee_id to rebuildable normalized records.

Examples:
  python scripts/repair_hr_import_employee_bindings.py --batch-id 4
  python scripts/repair_hr_import_employee_bindings.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.engine import engine
from app.services.hr_import_analytics_service import list_batches
from app.services.hr_import_employee_binding_service import repair_batch_employee_bindings
from app.services.hr_import_normalized_record_service import normalized_records_available


def _load_batch_ids(latest_only: bool) -> list[int]:
    with engine.connect() as conn:
        data = list_batches(conn)
    ids = [int(item["batch_id"]) for item in data["items"]]
    if latest_only:
        return ids[:1]
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair HR import employee bindings (ADR-039 3G)")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--all", action="store_true", help="Process every import batch")
    scope.add_argument("--latest", action="store_true", help="Process only the most recent batch")
    scope.add_argument("--batch-id", type=int, dest="batch_id", help="Process a single batch_id")
    args = parser.parse_args()

    with engine.connect() as conn:
        if not normalized_records_available(conn):
            print(
                "ERROR: hr_import_normalized_records table is missing. Run alembic upgrade head first.",
                file=sys.stderr,
            )
            return 1

    if args.batch_id is not None:
        batch_ids = [args.batch_id]
    else:
        batch_ids = _load_batch_ids(latest_only=args.latest)

    if not batch_ids:
        print("No import batches found.")
        return 0

    for batch_id in batch_ids:
        with engine.begin() as conn:
            summary = repair_batch_employee_bindings(conn, batch_id)
        print(json.dumps(summary, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
