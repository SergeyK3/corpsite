"""OPS-026.4 — one-time backfill for operational contacts missing after enrollment."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.engine import engine  # noqa: E402
from app.services.operational_contact_service import (  # noqa: E402
    ensure_operational_contact_for_employee,
    find_operational_contact_id,
    normalize_contact_full_name,
    parse_telegram_numeric_id,
)


def _load_candidates(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
                u.user_id,
                u.employee_id,
                u.full_name AS user_full_name,
                u.telegram_id,
                e.full_name AS employee_full_name,
                e.person_id AS employee_person_id
            FROM public.users u
            JOIN public.employees e ON e.employee_id = u.employee_id
            WHERE u.employee_id IS NOT NULL
              AND COALESCE(u.is_active, false) = true
            ORDER BY u.user_id
            """
        )
    ).mappings().all()

    candidates: list[dict[str, Any]] = []
    for row in rows:
        employee_id = int(row["employee_id"])
        full_name = str(row["employee_full_name"] or row["user_full_name"] or "").strip()
        telegram_numeric_id = parse_telegram_numeric_id(row.get("telegram_id"))
        person_id_raw = row.get("employee_person_id")
        person_id = int(person_id_raw) if person_id_raw not in (None, "") else None
        existing = find_operational_contact_id(
            conn,
            person_id=person_id,
            telegram_numeric_id=telegram_numeric_id,
            full_name=full_name,
        )
        if existing is not None:
            continue
        candidates.append(
            {
                "user_id": int(row["user_id"]),
                "employee_id": employee_id,
                "full_name": full_name,
                "normalized_name": normalize_contact_full_name(full_name),
                "telegram_numeric_id": telegram_numeric_id,
            }
        )
    return candidates


def _filter_candidates(
    candidates: list[dict[str, Any]],
    *,
    user_id: int | None,
    employee_id: int | None,
) -> list[dict[str, Any]]:
    filtered = candidates
    if user_id is not None:
        filtered = [item for item in filtered if item["user_id"] == user_id]
    if employee_id is not None:
        filtered = [item for item in filtered if item["employee_id"] == employee_id]
    return filtered


def _apply_requires_target_filter(*, apply: bool, user_id: int | None, employee_id: int | None) -> bool:
    """Return True when --apply is used without --user-id or --employee-id."""
    return apply and user_id is None and employee_id is None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill missing public.contacts rows for active users with employees.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create missing contacts. Requires --user-id or --employee-id.",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        metavar="ID",
        help="Target only this user_id (dry-run report or apply).",
    )
    parser.add_argument(
        "--employee-id",
        type=int,
        default=None,
        metavar="ID",
        help="Target only this employee_id (dry-run report or apply).",
    )
    args = parser.parse_args(argv)

    if _apply_requires_target_filter(
        apply=args.apply,
        user_id=args.user_id,
        employee_id=args.employee_id,
    ):
        print(
            "ERROR: --apply requires a target filter: --user-id or --employee-id.",
            file=sys.stderr,
        )
        return 2

    report: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry_run",
        "filter": {
            "user_id": args.user_id,
            "employee_id": args.employee_id,
        },
        "candidates": [],
        "created": [],
        "errors": [],
    }

    with engine.begin() as conn:
        all_candidates = _load_candidates(conn)
        candidates = _filter_candidates(
            all_candidates,
            user_id=args.user_id,
            employee_id=args.employee_id,
        )
        report["candidate_count"] = len(candidates)
        report["candidates"] = candidates

        if not args.apply:
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
            return 0

        for item in candidates:
            try:
                result = ensure_operational_contact_for_employee(
                    conn,
                    employee_id=int(item["employee_id"]),
                    full_name=str(item["full_name"]),
                )
                report["created"].append(
                    {
                        **item,
                        "contact_id": result.contact_id,
                        "contact_created": result.created,
                        "contact_existed": result.existed,
                    }
                )
            except Exception as exc:  # noqa: BLE001 — ops script collects row errors
                report["errors"].append({"employee_id": item["employee_id"], "error": str(exc)})

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
