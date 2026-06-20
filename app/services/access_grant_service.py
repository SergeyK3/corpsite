"""ADR-042 Phase B3 — access grant management (no enforcement)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.security_audit_service import write_security_event

TARGET_TYPES = frozenset({"PERSON", "ASSIGNMENT", "POSITION", "ORG_UNIT", "EMPLOYEE", "USER"})
SCOPE_TYPES = frozenset({"GLOBAL", "ORG_UNIT", "SELF"})


def _table_exists(conn: Connection, table: str) -> bool:
    return (
        conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table
                LIMIT 1
                """
            ),
            {"table": table},
        ).first()
        is not None
    )


def validate_grant_target(*, target_type: str, target_id: int, conn: Optional[Connection] = None) -> None:
    tt = (target_type or "").strip().upper()
    if tt not in TARGET_TYPES:
        raise ValueError(f"Invalid target_type: {target_type}")

    tid = int(target_id)
    checks = {
        "PERSON": ("persons", "person_id"),
        "ASSIGNMENT": ("person_assignments", "assignment_id"),
        "POSITION": ("positions", "position_id"),
        "ORG_UNIT": ("org_units", "unit_id"),
        "EMPLOYEE": ("employees", "employee_id"),
        "USER": ("users", "user_id"),
    }
    table, col = checks[tt]

    def _run(c: Connection) -> None:
        if not _table_exists(c, table):
            raise RuntimeError(f"Table {table} is not available")
        row = c.execute(
            text(f"SELECT 1 FROM public.{table} WHERE {col} = :tid LIMIT 1"),
            {"tid": tid},
        ).first()
        if not row:
            raise ValueError(f"Target not found: {tt} {tid}")

    if conn is not None:
        _run(conn)
    else:
        with engine.connect() as own_conn:
            _run(own_conn)


def create_security_audit_event(
    *,
    event_type: str,
    actor_user_id: Optional[int],
    metadata: Optional[Dict[str, Any]] = None,
    target_user_id: Optional[int] = None,
    conn: Optional[Connection] = None,
) -> Optional[int]:
    return write_security_event(
        event_type=event_type,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        metadata=metadata,
        conn=conn,
    )


def grant_access(
    *,
    access_role_id: int,
    target_type: str,
    target_id: int,
    granted_by_user_id: int,
    resource_key: str = "*",
    scope_type: str = "GLOBAL",
    scope_id: Optional[int] = None,
    include_subtree: bool = False,
    starts_at: Optional[datetime] = None,
    ends_at: Optional[datetime] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    tt = (target_type or "").strip().upper()
    st = (scope_type or "GLOBAL").strip().upper()
    if st not in SCOPE_TYPES:
        raise ValueError(f"Invalid scope_type: {scope_type}")
    if st == "ORG_UNIT" and scope_id is None:
        raise ValueError("scope_id is required when scope_type is ORG_UNIT")

    with engine.begin() as conn:
        validate_grant_target(target_type=tt, target_id=target_id, conn=conn)

        role_row = conn.execute(
            text(
                """
                SELECT access_role_id, code, access_level, level_rank
                FROM public.access_roles
                WHERE access_role_id = :id AND is_active = TRUE
                LIMIT 1
                """
            ),
            {"id": int(access_role_id)},
        ).mappings().first()
        if not role_row:
            raise ValueError(f"access_role_id not found or inactive: {access_role_id}")

        row = conn.execute(
            text(
                """
                INSERT INTO public.access_grants (
                    access_role_id,
                    target_type,
                    target_id,
                    resource_key,
                    scope_type,
                    scope_id,
                    include_subtree,
                    starts_at,
                    ends_at,
                    active_flag,
                    granted_by_user_id,
                    reason
                )
                VALUES (
                    :access_role_id,
                    :target_type,
                    :target_id,
                    :resource_key,
                    :scope_type,
                    :scope_id,
                    :include_subtree,
                    COALESCE(:starts_at, now()),
                    :ends_at,
                    TRUE,
                    :granted_by_user_id,
                    :reason
                )
                RETURNING grant_id, created_at
                """
            ),
            {
                "access_role_id": int(access_role_id),
                "target_type": tt,
                "target_id": int(target_id),
                "resource_key": resource_key or "*",
                "scope_type": st,
                "scope_id": int(scope_id) if scope_id is not None else None,
                "include_subtree": bool(include_subtree),
                "starts_at": starts_at,
                "ends_at": ends_at,
                "granted_by_user_id": int(granted_by_user_id),
                "reason": reason,
            },
        ).mappings().first()

        grant_id = int(row["grant_id"])
        audit_id = write_security_event(
            event_type="ACCESS_GRANTED",
            actor_user_id=int(granted_by_user_id),
            target_user_id=int(target_id) if tt == "USER" else None,
            metadata={
                "grant_id": grant_id,
                "access_role_code": role_row["code"],
                "target_type": tt,
                "target_id": int(target_id),
                "resource_key": resource_key or "*",
            },
            conn=conn,
        )

    return {
        "grant_id": grant_id,
        "access_role_id": int(access_role_id),
        "access_role_code": role_row["code"],
        "access_level": role_row["access_level"],
        "level_rank": int(role_row["level_rank"]),
        "target_type": tt,
        "target_id": int(target_id),
        "audit_id": audit_id,
    }


def revoke_access(
    *,
    grant_id: int,
    revoked_by_user_id: int,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    with engine.begin() as conn:
        existing = conn.execute(
            text(
                """
                SELECT
                    g.grant_id,
                    g.target_type,
                    g.target_id,
                    g.active_flag,
                    r.code AS access_role_code
                FROM public.access_grants g
                JOIN public.access_roles r ON r.access_role_id = g.access_role_id
                WHERE g.grant_id = :grant_id
                LIMIT 1
                """
            ),
            {"grant_id": int(grant_id)},
        ).mappings().first()
        if not existing:
            raise ValueError(f"Grant not found: {grant_id}")
        if not existing["active_flag"]:
            return {"grant_id": int(grant_id), "already_revoked": True}

        conn.execute(
            text(
                """
                UPDATE public.access_grants
                SET
                    active_flag = FALSE,
                    revoked_at = now(),
                    revoked_by_user_id = :revoked_by_user_id
                WHERE grant_id = :grant_id
                """
            ),
            {
                "grant_id": int(grant_id),
                "revoked_by_user_id": int(revoked_by_user_id),
            },
        )

        audit_id = write_security_event(
            event_type="ACCESS_REVOKED",
            actor_user_id=int(revoked_by_user_id),
            target_user_id=int(existing["target_id"]) if existing["target_type"] == "USER" else None,
            metadata={
                "grant_id": int(grant_id),
                "access_role_code": existing["access_role_code"],
                "target_type": existing["target_type"],
                "target_id": int(existing["target_id"]),
                "reason": reason,
            },
            conn=conn,
        )

    return {
        "grant_id": int(grant_id),
        "revoked": True,
        "audit_id": audit_id,
    }


def list_access_grants(
    *,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    filters = ["1=1"]
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if active_only:
        filters.append("g.active_flag = TRUE")
    if target_type:
        filters.append("g.target_type = :target_type")
        params["target_type"] = target_type.strip().upper()
    if target_id is not None:
        filters.append("g.target_id = :target_id")
        params["target_id"] = int(target_id)

    where_sql = " AND ".join(filters)

    with engine.connect() as conn:
        total = int(
            conn.execute(
                text(f"SELECT COUNT(*) FROM public.access_grants g WHERE {where_sql}"),
                params,
            ).scalar_one()
        )
        rows = conn.execute(
            text(
                f"""
                SELECT
                    g.grant_id,
                    g.access_role_id,
                    r.code AS access_role_code,
                    r.access_level,
                    r.level_rank,
                    g.target_type,
                    g.target_id,
                    g.resource_key,
                    g.scope_type,
                    g.scope_id,
                    g.include_subtree,
                    g.starts_at,
                    g.ends_at,
                    g.active_flag,
                    g.granted_by_user_id,
                    g.reason,
                    g.created_at,
                    g.revoked_at,
                    g.revoked_by_user_id
                FROM public.access_grants g
                JOIN public.access_roles r ON r.access_role_id = g.access_role_id
                WHERE {where_sql}
                ORDER BY g.grant_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

    items: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        for key in ("starts_at", "ends_at", "created_at", "revoked_at"):
            val = item.get(key)
            if isinstance(val, datetime):
                item[key] = val.isoformat()
        items.append(item)

    return {"items": items, "total": total, "limit": limit, "offset": offset}
