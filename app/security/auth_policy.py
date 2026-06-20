"""ADR-042 Phase B5 — auth policy helpers (lockout, token_version, must_change_password)."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Set

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.security_audit_service import write_security_event

PASSWORD_CHANGE_ALLOWED_PREFIXES: tuple[str, ...] = (
    "/auth/login",
    "/auth/password-change",
)


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "on"}


def login_max_failed_attempts() -> int:
    raw = _env("ADR042_LOGIN_MAX_FAILED_ATTEMPTS", "5")
    try:
        value = int(raw)
        return max(1, value)
    except Exception:
        return 5


def token_version_enforcement_enabled() -> bool:
    return _env_bool("ADR042_TOKEN_VERSION_ENFORCEMENT", default=False)


def must_change_password_enforcement_enabled() -> bool:
    return _env_bool("ADR042_MUST_CHANGE_PASSWORD_ENFORCEMENT", default=False)


def is_password_change_allowed_path(path: str) -> bool:
    normalized = (path or "").rstrip("/") or "/"
    for prefix in PASSWORD_CHANGE_ALLOWED_PREFIXES:
        base = prefix.rstrip("/")
        if normalized == base or normalized.startswith(base + "/"):
            return True
    return False


def require_password_not_expired_or_change_allowed(
    request: Request,
    user_ctx: Dict[str, Any],
) -> None:
    """Raise 403 when must_change_password enforcement blocks the request path."""
    if not must_change_password_enforcement_enabled():
        return
    if not user_ctx.get("must_change_password"):
        return
    if is_password_change_allowed_path(request.url.path):
        return
    raise HTTPException(status_code=403, detail="Password change required.")


def validate_token_version_claim(payload: Dict[str, Any], user_ctx: Dict[str, Any]) -> None:
    if not token_version_enforcement_enabled():
        return
    claim = payload.get("token_version")
    if claim is None:
        return
    db_version = int(user_ctx.get("token_version") or 1)
    if int(claim) != db_version:
        raise HTTPException(status_code=401, detail="Token invalidated.")


def _users_has_column(conn: Connection, column: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'users'
              AND column_name = :column
            LIMIT 1
            """
        ),
        {"column": column},
    ).first()
    return row is not None


def fetch_user_auth_policy_row(user_id: int) -> Optional[Dict[str, Any]]:
    with engine.connect() as conn:
        cols = {
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'users'
                    """
                )
            ).fetchall()
        }
        select_bits = [
            "user_id",
            "role_id",
            "unit_id",
            "is_active",
            "login",
            "password_hash",
        ]
        optional = (
            "locked_at",
            "locked_until",
            "locked_reason",
            "failed_login_count",
            "last_failed_login_at",
            "token_version",
            "must_change_password",
        )
        for col in optional:
            if col in cols:
                select_bits.append(col)

        row = conn.execute(
            text(
                f"""
                SELECT {", ".join(select_bits)}
                FROM public.users
                WHERE user_id = :uid
                LIMIT 1
                """
            ),
            {"uid": int(user_id)},
        ).mappings().first()
    return dict(row) if row else None


def fetch_user_auth_policy_row_by_login(login: str) -> Optional[Dict[str, Any]]:
    l = (login or "").strip().lower()
    if not l:
        return None
    with engine.connect() as conn:
        cols = {
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'users'
                    """
                )
            ).fetchall()
        }
        select_bits = [
            "user_id",
            "role_id",
            "unit_id",
            "is_active",
            "login",
            "password_hash",
        ]
        optional = (
            "locked_at",
            "locked_until",
            "locked_reason",
            "failed_login_count",
            "last_failed_login_at",
            "token_version",
            "must_change_password",
        )
        for col in optional:
            if col in cols:
                select_bits.append(col)

        row = conn.execute(
            text(
                f"""
                SELECT {", ".join(select_bits)}
                FROM public.users
                WHERE lower(login) = :login
                LIMIT 1
                """
            ),
            {"login": l},
        ).mappings().first()
    return dict(row) if row else None


def is_user_locked(user_row: Dict[str, Any]) -> bool:
    locked_at = user_row.get("locked_at")
    if locked_at is None:
        return False
    locked_until = user_row.get("locked_until")
    if locked_until is not None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        if hasattr(locked_until, "tzinfo") and locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if now >= locked_until:
            return False
    return True


def record_login_failed(
    *,
    user_id: Optional[int],
    login: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    failure_reason: str = "invalid_credentials",
) -> None:
    write_security_event(
        event_type="LOGIN_FAILED",
        actor_user_id=user_id,
        target_user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        success=False,
        failure_reason=failure_reason,
        metadata={"login": (login or "").strip().lower()},
    )

    if user_id is None:
        return

    threshold = login_max_failed_attempts()
    with engine.begin() as conn:
        if not _users_has_column(conn, "failed_login_count"):
            return

        row = conn.execute(
            text(
                """
                UPDATE public.users
                SET
                    failed_login_count = COALESCE(failed_login_count, 0) + 1,
                    last_failed_login_at = now()
                WHERE user_id = :uid
                RETURNING failed_login_count
                """
            ),
            {"uid": int(user_id)},
        ).first()
        if not row:
            return
        failed_count = int(row[0])

        if failed_count >= threshold and _users_has_column(conn, "locked_at"):
            conn.execute(
                text(
                    """
                    UPDATE public.users
                    SET
                        locked_at = now(),
                        locked_reason = 'brute_force'
                    WHERE user_id = :uid AND locked_at IS NULL
                    """
                ),
                {"uid": int(user_id)},
            )
            write_security_event(
                event_type="USER_LOCKED",
                actor_user_id=None,
                target_user_id=int(user_id),
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "reason": "brute_force",
                    "failed_login_count": failed_count,
                    "threshold": threshold,
                },
                conn=conn,
            )


def record_login_success(
    *,
    user_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    with engine.begin() as conn:
        sets = ["last_login_at = now()"] if _users_has_column(conn, "last_login_at") else []
        if _users_has_column(conn, "failed_login_count"):
            sets.append("failed_login_count = 0")
        if sets:
            conn.execute(
                text(f"UPDATE public.users SET {', '.join(sets)} WHERE user_id = :uid"),
                {"uid": int(user_id)},
            )

    write_security_event(
        event_type="LOGIN_SUCCESS",
        actor_user_id=int(user_id),
        target_user_id=int(user_id),
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={},
    )
