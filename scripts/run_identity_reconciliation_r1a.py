#!/usr/bin/env python3
"""Run ADR-044 R1a identity reconciliation (dry-run or execute).

Default mode is dry-run. Execute requires --actor-user-id and writes to local DB only
unless explicitly approved for production.

Examples:
  python scripts/run_identity_reconciliation_r1a.py --dry-run
  python scripts/run_identity_reconciliation_r1a.py --dry-run --output-json report.json
  python scripts/run_identity_reconciliation_r1a.py --execute --actor-user-id 1 --person-id 115 --limit 1
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
from app.services.identity_reconciliation_service import (
    IdentityReconciliationError,
    run_r1a_dry_run,
    run_r1a_execute,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="ADR-044 R1a identity reconciliation")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only (default when neither mode is set)",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Apply R1a materialization for APPLY candidates",
    )
    parser.add_argument("--snapshot-id", type=int, default=None, help="Canonical snapshot id")
    parser.add_argument(
        "--actor-user-id",
        type=int,
        default=None,
        help="Required for --execute (audit actor)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max APPLY candidates to process")
    parser.add_argument("--person-id", type=int, default=None, help="Restrict execute to one person")
    parser.add_argument("--output-json", type=str, default=None, help="Write JSON report to file")
    args = parser.parse_args()

    execute_mode = args.execute
    if not execute_mode and not args.dry_run:
        execute_mode = False

    try:
        with engine.connect() as conn:
            if execute_mode:
                if args.actor_user_id is None:
                    print("ERROR: --actor-user-id is required for --execute", file=sys.stderr)
                    return 2
                report = run_r1a_execute(
                    conn,
                    actor_user_id=int(args.actor_user_id),
                    snapshot_id=args.snapshot_id,
                    person_id=args.person_id,
                    limit=args.limit,
                )
            else:
                report = run_r1a_dry_run(conn, snapshot_id=args.snapshot_id)
    except IdentityReconciliationError as exc:
        print(f"ERROR: {exc.message}", file=sys.stderr)
        return 1

    payload = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.output_json:
        Path(args.output_json).write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {args.output_json}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
