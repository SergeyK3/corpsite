#!/usr/bin/env python3
"""OPS-009.18c — inspect and unlock locked admin account(s) on VPS.

Run on VPS from app root:

  cd /opt/projects/corpsite/app
  set -a && source .env && set +a
  ./venv/bin/python scripts/ops/ops_009_18c_admin_unlock.py snapshot admin
  ./venv/bin/python scripts/ops/ops_009_18c_admin_unlock.py unlock admin --execute
  ./venv/bin/python scripts/ops/ops_009_18c_admin_unlock.py verify admin

Default login is ``admin``. Only lock-state columns are changed on unlock.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

import app.config  # noqa: F401
from app.db.engine import engine
from app.security.auth_policy import is_user_locked
from app.services.security_audit_service import write_security_event
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID

DEFAULT_ADMIN_LOGIN = "admin"
OPS_ACTOR_USER_ID = 1

VERIFY_FIELD_NAMES = (
    "login",
    "role_id",
    "is_active",
    "failed_login_count",
    "locked_at",
    "locked_until",
    "locked_reason",
    "token_version",
    "must_change_password",
)


def _users_columns(conn) -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'users'
            """
        )
    ).fetchall()
    return {str(r[0]) for r in rows}


def user_verify_view(row: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Minimal user payload for snapshot/verify (no password fields)."""
    if not row:
        return None
    out: dict[str, Any] = {}
    for key in VERIFY_FIELD_NAMES:
        if key in row:
            out[key] = row.get(key)
    out["user_id"] = row.get("user_id")
    out["role_code"] = row.get("role_code")
    out["is_locked"] = is_user_locked(row)
    return out


def count_users_by_login(conn, login: str) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.users
                WHERE lower(login) = lower(:login)
                """
            ),
            {"login": login},
        ).scalar_one()
    )


def count_locked_users_by_login(conn, login: str) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.users
                WHERE lower(login) = lower(:login)
                  AND locked_at IS NOT NULL
                """
            ),
            {"login": login},
        ).scalar_one()
    )


def assert_single_unlock_target(conn, login: str) -> None:
    total = count_users_by_login(conn, login)
    if total == 0:
        raise RuntimeError(f"user not found: {login}")
    if total > 1:
        raise RuntimeError(
            f"ambiguous login {login!r}: {total} users match lower(login); aborting unlock"
        )
    locked = count_locked_users_by_login(conn, login)
    if locked > 1:
        raise RuntimeError(
            f"ambiguous locked login {login!r}: {locked} locked rows match; aborting unlock"
        )


def build_unlock_update_sql(cols: set[str]) -> str:
    sets = [
        "locked_at = NULL",
        "locked_reason = NULL",
        "token_version = COALESCE(token_version, 1) + 1",
    ]
    if "locked_until" in cols:
        sets.append("locked_until = NULL")
    if "failed_login_count" in cols:
        sets.append("failed_login_count = 0")
    return ", ".join(sets)


def _locked_users_snapshot(conn) -> list[dict[str, Any]]:
    cols = _users_columns(conn)
    optional = [
        c
        for c in (
            "locked_at",
            "locked_until",
            "locked_reason",
            "failed_login_count",
            "last_failed_login_at",
            "last_login_at",
            "must_change_password",
            "token_version",
        )
        if c in cols
    ]
    extra_sql = ", ".join(f"u.{c}" for c in optional)
    prefix = f"{extra_sql}, " if extra_sql else ""
    rows = conn.execute(
        text(
            f"""
            SELECT
                u.user_id,
                u.login,
                u.role_id,
                r.code AS role_code,
                r.name AS role_name,
                u.unit_id,
                u.is_active,
                {prefix}
                u.password_hash IS NOT NULL AS has_password
            FROM public.users u
            LEFT JOIN public.roles r ON r.role_id = u.role_id
            WHERE u.locked_at IS NOT NULL
            ORDER BY u.user_id
            """
        )
    ).mappings().all()
    return [user_verify_view(dict(row)) or {} for row in rows]


def _user_by_login_snapshot(conn, login: str) -> Optional[dict[str, Any]]:
    cols = _users_columns(conn)
    optional = [
        c
        for c in (
            "locked_at",
            "locked_until",
            "locked_reason",
            "failed_login_count",
            "last_failed_login_at",
            "last_login_at",
            "must_change_password",
            "token_version",
        )
        if c in cols
    ]
    extra_sql = ", ".join(f"u.{c}" for c in optional)
    prefix = f"{extra_sql}, " if extra_sql else ""
    row = conn.execute(
        text(
            f"""
            SELECT
                u.user_id,
                u.login,
                u.role_id,
                r.code AS role_code,
                r.name AS role_name,
                u.unit_id,
                u.is_active,
                {prefix}
                u.password_hash IS NOT NULL AS has_password
            FROM public.users u
            LEFT JOIN public.roles r ON r.role_id = u.role_id
            WHERE lower(u.login) = lower(:login)
            LIMIT 1
            """
        ),
        {"login": login},
    ).mappings().first()
    return user_verify_view(dict(row) if row else None)


def _admin_candidates_snapshot(conn) -> list[dict[str, Any]]:
    cols = _users_columns(conn)
    optional = [
        c
        for c in (
            "locked_at",
            "locked_until",
            "locked_reason",
            "failed_login_count",
            "last_login_at",
            "must_change_password",
            "token_version",
        )
        if c in cols
    ]
    extra_sql = ", ".join(f"u.{c}" for c in optional)
    prefix = f"{extra_sql}, " if extra_sql else ""
    rows = conn.execute(
        text(
            f"""
            SELECT
                u.user_id,
                u.login,
                u.role_id,
                r.code AS role_code,
                r.name AS role_name,
                u.is_active,
                u.unit_id,
                {prefix}
                1 AS _pad
            FROM public.users u
            LEFT JOIN public.roles r ON r.role_id = u.role_id
            WHERE u.role_id = :admin_role_id
               OR lower(r.code) IN ('admin', 'system_admin')
               OR lower(u.login) IN ('admin', 'administrator', 'sysadmin')
            ORDER BY u.user_id
            """
        ),
        {"admin_role_id": int(SYSTEM_ADMIN_ROLE_ID)},
    ).mappings().all()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item.pop("_pad", None)
        view = user_verify_view(item)
        if view:
            view["unit_id"] = item.get("unit_id")
            out.append(view)
    return out


def _recent_lock_events(conn, *, login: str, limit: int = 10) -> list[dict[str, Any]]:
    if not conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'security_audit_log'
            LIMIT 1
            """
        )
    ).first():
        return []

    rows = conn.execute(
        text(
            """
            SELECT
                e.audit_id,
                e.event_type,
                e.happened_at,
                e.actor_user_id,
                e.target_user_id,
                e.failure_reason,
                e.metadata
            FROM public.security_audit_log e
            JOIN public.users u ON u.user_id = e.target_user_id
            WHERE lower(u.login) = lower(:login)
              AND e.event_type IN ('USER_LOCKED', 'USER_UNLOCKED', 'LOGIN_FAILED')
            ORDER BY e.audit_id DESC
            LIMIT :limit
            """
        ),
        {"login": login, "limit": int(limit)},
    ).mappings().all()
    return [dict(r) for r in rows]


def _api_login_probe(login: str, api_base: str, password: str = "") -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/auth/login"
    payload = {"login": login, "password": password or "probe-invalid-password"}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    result: dict[str, Any] = {"url": url, "login": login}
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            result["http_status"] = resp.status
            result["detail"] = "login_ok"
            result["has_access_token"] = bool(body.get("access_token"))
    except urllib.error.HTTPError as exc:
        result["http_status"] = exc.code
        try:
            body = json.loads(exc.read().decode("utf-8"))
            result["detail"] = body.get("detail")
        except Exception:
            result["detail"] = exc.reason
    except Exception as exc:
        result["error"] = str(exc)
    return result


def build_snapshot(*, login: str, api_base: str) -> dict[str, Any]:
    with engine.connect() as conn:
        locked = _locked_users_snapshot(conn)
        admin_candidates = _admin_candidates_snapshot(conn)
        target = _user_by_login_snapshot(conn, login)
        lock_events = _recent_lock_events(conn, login=login)
        login_match_count = count_users_by_login(conn, login)
        locked_match_count = count_locked_users_by_login(conn, login)

    return {
        "login": login,
        "login_match_count": login_match_count,
        "locked_match_count": locked_match_count,
        "locked_users": locked,
        "admin_candidates": admin_candidates,
        "target_user": target,
        "recent_lock_events": lock_events,
        "lock_mechanism": {
            "table": "public.users",
            "fields": list(VERIFY_FIELD_NAMES),
            "unlock_mutates_only": [
                "locked_at",
                "locked_until",
                "locked_reason",
                "failed_login_count",
                "token_version",
            ],
            "auto_lock_threshold_env": "ADR042_LOGIN_MAX_FAILED_ATTEMPTS",
            "auto_lock_reason": "brute_force",
        },
        "api_login_probe_invalid_password": _api_login_probe(login, api_base),
    }


def unlock_user_tx(conn, *, login: str, actor_user_id: int) -> int:
    assert_single_unlock_target(conn, login)
    locked_count = count_locked_users_by_login(conn, login)
    if locked_count == 0:
        return 0

    cols = _users_columns(conn)
    set_sql = build_unlock_update_sql(cols)
    result = conn.execute(
        text(
            f"""
            UPDATE public.users
            SET {set_sql}
            WHERE lower(login) = lower(:login)
              AND locked_at IS NOT NULL
            """
        ),
        {"login": login},
    )
    rows = int(result.rowcount or 0)
    if rows != 1:
        raise RuntimeError(
            f"unlock updated {rows} row(s) for login {login!r}; expected exactly 1"
        )

    target_user_id = conn.execute(
        text(
            """
            SELECT user_id
            FROM public.users
            WHERE lower(login) = lower(:login)
            LIMIT 1
            """
        ),
        {"login": login},
    ).scalar_one()

    write_security_event(
        event_type="USER_UNLOCKED",
        actor_user_id=int(actor_user_id),
        target_user_id=int(target_user_id),
        metadata={"source": "ops_009_18c_admin_unlock"},
        conn=conn,
    )
    return rows


def _resolve_login(args: argparse.Namespace) -> str:
    if getattr(args, "login_pos", None):
        return str(args.login_pos).strip()
    return str(args.login).strip()


def cmd_snapshot(args: argparse.Namespace) -> int:
    login = _resolve_login(args)
    out = build_snapshot(login=login, api_base=args.api_base)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_unlock(args: argparse.Namespace) -> int:
    login = _resolve_login(args)
    before = build_snapshot(login=login, api_base=args.api_base)
    target = before.get("target_user")
    if not target:
        print(json.dumps({"error": f"user not found: {login}"}, ensure_ascii=False, indent=2))
        return 1

    if before.get("login_match_count", 0) > 1:
        print(
            json.dumps(
                {
                    "error": f"ambiguous login {login!r}: {before['login_match_count']} users match",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    if not target.get("is_locked"):
        out = {
            "mode": "noop",
            "message": "User is not locked; no changes applied",
            "target_user": target,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 0

    if not args.execute:
        out = {
            "mode": "dry_run",
            "target_user": target,
            "fields_to_clear": [
                "locked_at",
                "locked_until",
                "locked_reason",
            ],
            "fields_to_reset": ["failed_login_count"],
            "fields_to_increment": ["token_version"],
            "fields_unchanged": [
                "password_hash",
                "role_id",
                "unit_id",
                "is_active",
                "must_change_password",
            ],
            "where_clause": "lower(login) = lower(:login) AND locked_at IS NOT NULL",
            "message": "Pass --execute to unlock",
        }
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 0

    try:
        with engine.begin() as conn:
            rows = unlock_user_tx(conn, login=login, actor_user_id=OPS_ACTOR_USER_ID)
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    after = build_snapshot(login=login, api_base=args.api_base)
    out = {
        "mode": "executed",
        "rows_updated": rows,
        "target_login": login,
        "before_target_user": before.get("target_user"),
        "after_target_user": after.get("target_user"),
        "recent_lock_events_after": after.get("recent_lock_events"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0 if rows == 1 else 1


def cmd_verify(args: argparse.Namespace) -> int:
    login = _resolve_login(args)
    out = build_snapshot(login=login, api_base=args.api_base)
    target = out.get("target_user") or {}
    probe = out.get("api_login_probe_invalid_password") or {}

    checks = {
        "user_exists": bool(target),
        "single_login_match": out.get("login_match_count") == 1,
        "user_active": bool(target.get("is_active")),
        "not_locked_in_db": not bool(target.get("is_locked")),
        "locked_at_null": target.get("locked_at") is None,
        "locked_until_null_or_missing": target.get("locked_until") in (None, ""),
        "locked_reason_null_or_missing": target.get("locked_reason") in (None, ""),
        "login_not_account_locked": probe.get("detail") != "Account locked.",
    }
    out["verification_checks"] = checks
    out["all_checks_pass"] = all(checks.values())
    out["verdict"] = "UNLOCK VERIFIED" if out["all_checks_pass"] else "UNLOCK FAILED"
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0 if out["all_checks_pass"] else 1


def main() -> int:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--login", default=DEFAULT_ADMIN_LOGIN)
    parent.add_argument("--api-base", default="http://127.0.0.1:8000")

    parser = argparse.ArgumentParser(description="OPS-009.18c admin account unlock")
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name, help_text in (
        ("snapshot", "Read-only lock state snapshot"),
        ("verify", "Post-unlock verification"),
    ):
        p = sub.add_parser(name, parents=[parent], help=help_text)
        p.add_argument(
            "login_pos",
            nargs="?",
            default=None,
            help=f"login to inspect (default: {DEFAULT_ADMIN_LOGIN})",
        )

    p_unlock = sub.add_parser("unlock", parents=[parent], help="Unlock account (dry-run unless --execute)")
    p_unlock.add_argument(
        "login_pos",
        nargs="?",
        default=None,
        help=f"login to unlock (default: {DEFAULT_ADMIN_LOGIN})",
    )
    p_unlock.add_argument("--execute", action="store_true")

    args = parser.parse_args()
    if args.cmd == "snapshot":
        return cmd_snapshot(args)
    if args.cmd == "unlock":
        return cmd_unlock(args)
    if args.cmd == "verify":
        return cmd_verify(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
