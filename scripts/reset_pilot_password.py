#!/usr/bin/env python3
"""One-off: reset QM pilot account passwords (default: Corp2026!).

Does not touch admin or other non-QM users.

Usage on VPS:
  export $(grep -v '^#' /etc/corpsite/.env | xargs)
  ./venv/bin/python scripts/reset_pilot_password.py --yes
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

import app.config  # noqa: F401
from app.auth import hash_password
from app.db.engine import engine

QM_PILOT_LOGINS = (
    "qm_head@corp.local",
    "qm_hosp@corp.local",
    "qm_amb@corp.local",
    "qm_complaint_reg@corp.local",
    "qm_complaint_pat@corp.local",
)

DEFAULT_PASSWORD = "Corp2026!"


def _normalize_login(login: str) -> str:
    return (login or "").strip().lower()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset QM pilot user passwords (admin is not changed).",
    )
    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help=f"New password for QM accounts (default: {DEFAULT_PASSWORD!r})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show matched users without updating password_hash",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Apply changes without interactive confirmation",
    )
    args = parser.parse_args()

    password = (args.password or "").strip()
    if not password:
        print("Password must not be empty", file=sys.stderr)
        return 2

    logins = [_normalize_login(x) for x in QM_PILOT_LOGINS]
    placeholders = ", ".join(f":login_{i}" for i in range(len(logins)))
    params = {f"login_{i}": login for i, login in enumerate(logins)}

    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    f"""
                    SELECT user_id, login, is_active
                    FROM public.users
                    WHERE lower(login) IN ({placeholders})
                    ORDER BY login
                    """
                ),
                params,
            )
            .mappings()
            .all()
        )

    found = {_normalize_login(str(r["login"])) for r in rows}
    missing = [login for login in logins if login not in found]

    if missing:
        print("Missing QM pilot accounts in DB:", ", ".join(missing), file=sys.stderr)

    if not rows:
        print("No QM pilot users found; nothing to do.", file=sys.stderr)
        return 1

    print("Matched users:")
    for row in rows:
        active = "active" if row.get("is_active") else "inactive"
        print(f"  - {row['login']} (user_id={row['user_id']}, {active})")

    if args.dry_run:
        print("Dry-run: password_hash not updated.")
        return 0

    if not args.yes:
        answer = input(f"Reset passwords for {len(rows)} user(s) to the new value? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Aborted.")
            return 0

    new_hash = hash_password(password)
    with engine.begin() as conn:
        result = conn.execute(
            text(
                f"""
                UPDATE public.users
                SET password_hash = :password_hash
                WHERE lower(login) IN ({placeholders})
                """
            ),
            {**params, "password_hash": new_hash},
        )

    updated = int(getattr(result, "rowcount", 0) or 0)
    print(f"Updated password_hash for {updated} QM pilot user(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
