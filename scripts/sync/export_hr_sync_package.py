#!/usr/bin/env python3
"""Export HR sync package from database (ADR-038 Phase B.2)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.engine import engine
from app.services.sync.export_service import SyncExportError, export_hr_sync_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Corpsite HR sync package from database")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for output zip")
    parser.add_argument("--source-instance-id", required=True, help="Source instance identifier")
    parser.add_argument("--source-org-id", required=True, help="Source organization id")
    parser.add_argument("--source-org-name", required=True, help="Source organization name")
    parser.add_argument(
        "--environment",
        default="server",
        choices=["server", "local", "staging"],
        help="Export environment label for metadata.json",
    )
    parser.add_argument("--notes", default=None, help="Optional export notes")
    parser.add_argument("--exported-by-user-login", default=None, help="Optional exporter login for metadata")
    args = parser.parse_args()

    try:
        with engine.connect() as conn:
            result = export_hr_sync_package(
                conn,
                output_dir=args.output_dir,
                source_instance_id=args.source_instance_id,
                source_organization={
                    "id": args.source_org_id,
                    "name": args.source_org_name,
                },
                environment=args.environment,
                notes=args.notes,
                exported_by_user_login=args.exported_by_user_login,
            )
    except SyncExportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(result.output_path)
    print(f"employees={result.employee_count}")
    print(f"overrides={result.override_count}")
    print(f"skipped_overrides={result.skipped_override_count}")
    print(f"validation_ok={result.validation_ok}")
    for warning in result.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    return 0 if result.validation_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
