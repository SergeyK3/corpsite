"""ADR-042 Phase B4 — minimal sysadmin user management."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.db.engine import engine
from app.services.security_audit_service import write_security_event

_USER_COLUMNS = """
    u.user_id,
    u.employee_id,
    u.full_name,
    u.login,
    u.role_id,
    r.name AS role_name,
    u.unit_id,
    u.is_active,
    u.must_change_password,
    u.locked_at,
    u.locked_reason,
    u.token_version,
    u.created_at
"""


def _serialize_user(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    for key in ("locked_at", "created_at"):
        val = out.get(key)
        if isinstance(val, datetime):
            out[key] = val.isoformat()
    out.pop("password", None)
    out.pop("password_hash", None)
    return out


def _fetch_user(conn, user_id: int) -> Optional[Dict[str, Any]]:
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
    select_cols = [c.strip() for c in _USER_COLUMNS.replace("\n", " ").split(",") if c.strip()]
    filtered = []
    for expr in select_cols:
        base = expr.split(" AS ")[0].strip().split(".")[-1]
        if base.startswith("r."):
            filtered.append(expr)
        elif base in cols or expr.startswith("r."):
            filtered.append(expr)

    sql = f"""
        SELECT {", ".join(filtered)}
        FROM public.users u
        LEFT JOIN public.roles r ON r.role_id = u.role_id
        WHERE u.user_id = :user_id
        LIMIT 1
    """
    row = conn.execute(text(sql), {"user_id": int(user_id)}).mappings().first()
    return dict(row) if row else None


def list_admin_users(*, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))

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
        extra = []
        if "must_change_password" in cols:
            extra.append("u.must_change_password")
        if "locked_at" in cols:
            extra.append("u.locked_at")
        if "locked_reason" in cols:
            extra.append("u.locked_reason")
        if "token_version" in cols:
            extra.append("u.token_version")

        base_select = """
            u.user_id,
            u.employee_id,
            u.full_name,
            u.login,
            u.role_id,
            r.name AS role_name,
            u.unit_id,
            u.is_active,
            u.created_at
        """
        if extra:
            base_select = base_select.rstrip() + ",\n            " + ",\n            ".join(extra)

        total = int(conn.execute(text("SELECT COUNT(*) FROM public.users")).scalar_one())
        rows = conn.execute(
            text(
                f"""
                SELECT {base_select}
                FROM public.users u
                LEFT JOIN public.roles r ON r.role_id = u.role_id
                ORDER BY u.user_id
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": limit, "offset": offset},
        ).mappings().all()

    items = [_serialize_user(dict(r)) for r in rows]
    for item in items:
        item.setdefault("must_change_password", False)
        item.setdefault("token_version", 1)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_admin_user(user_id: int) -> Dict[str, Any]:
    with engine.connect() as conn:
        row = _fetch_user(conn, int(user_id))
    if not row:
        raise ValueError(f"User not found: {user_id}")
    out = _serialize_user(row)
    out.setdefault("must_change_password", False)
    out.setdefault("token_version", 1)
    return out


def lock_user(*, user_id: int, actor_user_id: int, reason: str = "admin") -> Dict[str, Any]:
    allowed = {"brute_force", "admin", "policy", "security"}
    lock_reason = (reason or "admin").strip().lower()
    if lock_reason not in allowed:
        raise ValueError(f"Invalid locked_reason: {reason}")

    with engine.begin() as conn:
        row = _fetch_user(conn, int(user_id))
        if not row:
            raise ValueError(f"User not found: {user_id}")

        conn.execute(
            text(
                """
                UPDATE public.users
                SET
                    locked_at = now(),
                    locked_reason = :locked_reason,
                    token_version = COALESCE(token_version, 1) + 1
                WHERE user_id = :user_id
                """
            ),
            {"user_id": int(user_id), "locked_reason": lock_reason},
        )

        audit_id = write_security_event(
            event_type="USER_LOCKED",
            actor_user_id=int(actor_user_id),
            target_user_id=int(user_id),
            metadata={"locked_reason": lock_reason},
            conn=conn,
        )

    updated = get_admin_user(int(user_id))
    return {**updated, "audit_id": audit_id}


def unlock_user(*, user_id: int, actor_user_id: int) -> Dict[str, Any]:
    with engine.begin() as conn:
        row = _fetch_user(conn, int(user_id))
        if not row:
            raise ValueError(f"User not found: {user_id}")

        conn.execute(
            text(
                """
                UPDATE public.users
                SET
                    locked_at = NULL,
                    locked_until = NULL,
                    locked_reason = NULL,
                    token_version = COALESCE(token_version, 1) + 1
                WHERE user_id = :user_id
                """
            ),
            {"user_id": int(user_id)},
        )

        audit_id = write_security_event(
            event_type="USER_UNLOCKED",
            actor_user_id=int(actor_user_id),
            target_user_id=int(user_id),
            metadata={},
            conn=conn,
        )

    updated = get_admin_user(int(user_id))
    return {**updated, "audit_id": audit_id}


def force_password_change(*, user_id: int, actor_user_id: int) -> Dict[str, Any]:
    with engine.begin() as conn:
        row = _fetch_user(conn, int(user_id))
        if not row:
            raise ValueError(f"User not found: {user_id}")

        conn.execute(
            text(
                """
                UPDATE public.users
                SET
                    must_change_password = TRUE,
                    token_version = COALESCE(token_version, 1) + 1
                WHERE user_id = :user_id
                """
            ),
            {"user_id": int(user_id)},
        )

        audit_id = write_security_event(
            event_type="PASSWORD_CHANGED",
            actor_user_id=int(actor_user_id),
            target_user_id=int(user_id),
            metadata={"action": "force_password_change"},
            conn=conn,
        )

    updated = get_admin_user(int(user_id))
    return {**updated, "audit_id": audit_id}
