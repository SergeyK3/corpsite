#!/usr/bin/env python3
"""Preview HR sync package import diff (ADR-038 Phase B.4)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.engine import engine
from app.services.sync.preview_service import preview_hr_sync_package, preview_result_to_dict


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview Corpsite HR sync package import diff")
    parser.add_argument("--package", required=True, type=Path, help="Path to sync package zip")
    parser.add_argument("--json", action="store_true", help="Print full preview result as JSON")
    args = parser.parse_args()

    with engine.connect() as conn:
        result = preview_hr_sync_package(conn, package_path=args.package)

    if args.json:
        print(json.dumps(preview_result_to_dict(result), ensure_ascii=False, indent=2))
    else:
        print(f"validation_ok={result.validation_ok}")
        print(f"total_records={result.total_records}")
        print(f"new={result.new_count}")
        print(f"update={result.update_count}")
        print(f"merge={result.merge_count}")
        print(f"identical={result.identical_count}")
        print(f"orphan={result.orphan_count}")
        print(f"ambiguous={result.ambiguous_count}")
        print(f"conflict={result.conflict_count}")
        print(f"skipped={result.skipped_count}")
        print(f"apply_allowed={result.apply_allowed_count}")

    for warning in result.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)

    return 0 if result.validation_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
