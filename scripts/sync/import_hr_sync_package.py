#!/usr/bin/env python3
"""Import HR sync package into database (ADR-038 Phase B.3)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.engine import engine
from app.services.sync.import_service import SyncImportError, import_hr_sync_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Corpsite HR sync package into database")
    parser.add_argument("--package", required=True, type=Path, help="Path to sync package zip")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Validate and resolve without DB writes")
    mode.add_argument("--apply", action="store_true", help="Apply overrides to database")
    args = parser.parse_args()

    try:
        if args.apply:
            with engine.begin() as conn:
                result = import_hr_sync_package(
                    conn,
                    package_path=args.package,
                    apply_changes=True,
                )
        else:
            with engine.connect() as conn:
                result = import_hr_sync_package(
                    conn,
                    package_path=args.package,
                    apply_changes=False,
                )
    except SyncImportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"package={result.package_path}")
    print(f"validation_ok={result.validation_ok}")
    print(f"dry_run={result.dry_run}")
    print(f"employee_records={result.employee_records}")
    print(f"override_records={result.override_records}")
    print(f"resolved={result.resolved_count}")
    print(f"orphan={result.orphan_count}")
    print(f"ambiguous={result.ambiguous_count}")
    print(f"applied={result.applied_count}")
    print(f"skipped={result.skipped_count}")

    for warning in result.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if not result.validation_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
