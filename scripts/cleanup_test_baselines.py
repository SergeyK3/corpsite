#!/usr/bin/env python3
"""One-time cleanup of pytest/sample-workbook HR import artifacts from shared dev DB."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.engine import engine
from tests.hr_import_fixtures import (
    cleanup_orphan_test_import_batches,
    cleanup_orphan_test_publication_origins,
    cleanup_sample_workbook_baselines,
    find_orphan_test_import_batches,
    find_orphan_test_publication_origin_ids,
    find_sample_workbook_baseline_ids,
    is_sample_workbook_baseline,
    is_sample_workbook_import_batch,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply deletion. Without this flag the script runs in dry-run mode.",
    )
    args = parser.parse_args()

    with engine.begin() as conn:
        baseline_candidates = find_sample_workbook_baseline_ids(conn)
        origin_candidates = find_orphan_test_publication_origin_ids(conn)
        batch_candidates = find_orphan_test_import_batches(conn)

        if not baseline_candidates and not origin_candidates and not batch_candidates:
            print("No sample-workbook baselines, orphan origins, or pytest import batches found.")
            return 0

        if baseline_candidates:
            print("Sample-workbook baseline candidates:")
            for baseline_id in baseline_candidates:
                print(f"  - baseline_id={baseline_id} (sample fingerprint match)")

        if origin_candidates:
            print("Orphan test PublicationOrigin candidates:")
            for origin_id in origin_candidates:
                print(f"  - publication_origin_id={origin_id} (no baseline, small entry_count)")

        if batch_candidates:
            print("Orphan pytest import batch candidates:")
            for row in batch_candidates:
                print(
                    "  - import_code={import_code} rows={total_rows} status={status}".format(
                        import_code=row["import_code"],
                        total_rows=row["total_rows"],
                        status=row["status"],
                    )
                )

        if not args.execute:
            print("\nDry run only. Re-run with --execute to delete these artifacts.")
            return 0

        removed_baselines = cleanup_sample_workbook_baselines(conn)
        removed_origins = cleanup_orphan_test_publication_origins(conn)
        removed_import_codes = cleanup_orphan_test_import_batches(conn)
        print(f"\nRemoved {len(removed_baselines)} baseline(s): {removed_baselines}")
        print(f"Removed {len(removed_origins)} orphan origin(s): {removed_origins}")
        print(f"Removed {len(removed_import_codes)} import batch(es): {removed_import_codes}")

        remaining = find_sample_workbook_baseline_ids(conn)
        if remaining:
            print(f"WARNING: still detected sample baselines: {remaining}")
            return 1
        remaining_origins = find_orphan_test_publication_origin_ids(conn)
        if remaining_origins:
            print(f"WARNING: still detected orphan test origins: {remaining_origins}")
            return 1
        remaining_batches = find_orphan_test_import_batches(conn)
        if remaining_batches:
            codes = [str(row["import_code"]) for row in remaining_batches]
            print(f"WARNING: still detected orphan pytest import batches: {codes}")
            return 1

        with engine.connect() as verify_conn:
            from sqlalchemy import text

            for baseline_id in (241, 333):
                if is_sample_workbook_baseline(verify_conn, baseline_id):
                    print(f"WARNING: production baseline {baseline_id} matched sample fingerprint")
                    return 1
            for import_code in ("2606-02",):
                row = verify_conn.execute(
                    text("SELECT batch_id FROM hr_import_batches WHERE import_code = :import_code"),
                    {"import_code": import_code},
                ).first()
                if row and is_sample_workbook_import_batch(verify_conn, int(row[0])):
                    print(f"WARNING: import {import_code} matched sample-workbook batch fingerprint")
                    return 1

        print("Cleanup completed. Production imports and migrated baselines were not matched.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
