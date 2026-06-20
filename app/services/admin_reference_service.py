"""ADR-042 Phase C1.1 — read-only reference data for sysadmin access UI."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.db.engine import engine
from app.security.admin_guard import admin_guard_mode


def _table_exists(conn, table: str) -> bool:
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


def list_access_roles(*, active_only: bool = True) -> List[Dict[str, Any]]:
    with engine.connect() as conn:
        if not _table_exists(conn, "access_roles"):
            return []

        filters = ["1=1"]
        if active_only:
            filters.append("is_active = TRUE")
        where_sql = " AND ".join(filters)

        rows = conn.execute(
            text(
                f"""
                SELECT
                    access_role_id,
                    code,
                    name AS label,
                    description,
                    access_level,
                    level_rank,
                    is_active AS active_flag
                FROM public.access_roles
                WHERE {where_sql}
                ORDER BY level_rank, code
                """
            )
        ).mappings().all()

    return [dict(r) for r in rows]


def get_guard_mode_info() -> Dict[str, Any]:
    mode = admin_guard_mode()
    messages = {
        "legacy": "Стандартный режим: доступ по legacy privileged (role_id=2 / env allowlist).",
        "access_grants_shadow": "Режим проверки прав: shadow.",
        "access_grants_enforced": "Режим принудительной проверки прав включён.",
    }
    return {
        "guard_mode": mode,
        "message": messages.get(mode, messages["legacy"]),
        "enforcement_active": mode == "access_grants_enforced",
        "shadow_mode": mode == "access_grants_shadow",
    }


def search_access_targets(
    *,
    q: str,
    target_type: str,
    limit: int = 20,
) -> Dict[str, Any]:
    tt = (target_type or "").strip().upper()
    allowed = {"USER", "EMPLOYEE", "PERSON", "ASSIGNMENT", "POSITION", "ORG_UNIT"}
    if tt not in allowed:
        raise ValueError(f"Invalid target_type: {target_type}")

    limit = max(1, min(int(limit), 50))
    query = (q or "").strip()
    like = f"%{query.lower()}%" if query else "%"

    with engine.connect() as conn:
        if tt == "USER":
            if not _table_exists(conn, "users"):
                return {"items": [], "target_type": tt, "q": query}
            rows = conn.execute(
                text(
                    """
                    SELECT
                        u.user_id AS target_id,
                        COALESCE(u.login, u.full_name, 'user') AS label,
                        COALESCE(u.full_name, '') AS subtitle,
                        jsonb_build_object(
                            'login', u.login,
                            'role_id', u.role_id,
                            'is_active', u.is_active
                        ) AS metadata
                    FROM public.users u
                    WHERE (
                        :empty_q
                        OR lower(COALESCE(u.login, '')) LIKE :like
                        OR lower(COALESCE(u.full_name, '')) LIKE :like
                        OR CAST(u.user_id AS text) LIKE :like
                    )
                    ORDER BY u.user_id
                    LIMIT :limit
                    """
                ),
                {"like": like, "limit": limit, "empty_q": not query},
            ).mappings().all()

        elif tt == "EMPLOYEE":
            if not _table_exists(conn, "employees"):
                return {"items": [], "target_type": tt, "q": query}
            rows = conn.execute(
                text(
                    """
                    SELECT
                        e.employee_id AS target_id,
                        COALESCE(e.full_name, 'employee') AS label,
                        COALESCE('person_id=' || e.person_id::text, '') AS subtitle,
                        jsonb_build_object(
                            'person_id', e.person_id,
                            'org_unit_id', e.org_unit_id,
                            'is_active', e.is_active
                        ) AS metadata
                    FROM public.employees e
                    WHERE (
                        :empty_q
                        OR lower(COALESCE(e.full_name, '')) LIKE :like
                        OR CAST(e.employee_id AS text) LIKE :like
                    )
                    ORDER BY e.employee_id
                    LIMIT :limit
                    """
                ),
                {"like": like, "limit": limit, "empty_q": not query},
            ).mappings().all()

        elif tt == "PERSON":
            if not _table_exists(conn, "persons"):
                return {"items": [], "target_type": tt, "q": query}
            rows = conn.execute(
                text(
                    """
                    SELECT
                        p.person_id AS target_id,
                        COALESCE(p.full_name, 'person') AS label,
                        COALESCE(p.match_key, '') AS subtitle,
                        jsonb_build_object(
                            'person_status', p.person_status,
                            'source', p.source
                        ) AS metadata
                    FROM public.persons p
                    WHERE (
                        :empty_q
                        OR lower(COALESCE(p.full_name, '')) LIKE :like
                        OR lower(COALESCE(p.match_key, '')) LIKE :like
                        OR CAST(p.person_id AS text) LIKE :like
                    )
                    ORDER BY p.person_id
                    LIMIT :limit
                    """
                ),
                {"like": like, "limit": limit, "empty_q": not query},
            ).mappings().all()

        elif tt == "ASSIGNMENT":
            if not _table_exists(conn, "person_assignments"):
                return {"items": [], "target_type": tt, "q": query}
            rows = conn.execute(
                text(
                    """
                    SELECT
                        pa.assignment_id AS target_id,
                        COALESCE(p.full_name, 'assignment') AS label,
                        COALESCE(
                            'person #' || pa.person_id::text || ' · primary=' || pa.is_primary::text,
                            ''
                        ) AS subtitle,
                        jsonb_build_object(
                            'person_id', pa.person_id,
                            'org_unit_id', pa.org_unit_id,
                            'position_id', pa.position_id,
                            'lifecycle_status', pa.lifecycle_status
                        ) AS metadata
                    FROM public.person_assignments pa
                    LEFT JOIN public.persons p ON p.person_id = pa.person_id
                    WHERE (
                        :empty_q
                        OR lower(COALESCE(p.full_name, '')) LIKE :like
                        OR CAST(pa.assignment_id AS text) LIKE :like
                        OR CAST(pa.person_id AS text) LIKE :like
                    )
                    ORDER BY pa.assignment_id DESC
                    LIMIT :limit
                    """
                ),
                {"like": like, "limit": limit, "empty_q": not query},
            ).mappings().all()

        elif tt == "POSITION":
            if not _table_exists(conn, "positions"):
                return {"items": [], "target_type": tt, "q": query}
            rows = conn.execute(
                text(
                    """
                    SELECT
                        p.position_id AS target_id,
                        COALESCE(p.name, 'position') AS label,
                        COALESCE(p.category, '') AS subtitle,
                        jsonb_build_object('category', p.category) AS metadata
                    FROM public.positions p
                    WHERE (
                        :empty_q
                        OR lower(COALESCE(p.name, '')) LIKE :like
                        OR CAST(p.position_id AS text) LIKE :like
                    )
                    ORDER BY p.position_id
                    LIMIT :limit
                    """
                ),
                {"like": like, "limit": limit, "empty_q": not query},
            ).mappings().all()

        else:  # ORG_UNIT
            table = "org_units" if _table_exists(conn, "org_units") else None
            if table is None and _table_exists(conn, "units"):
                table = "units"
            if table is None:
                return {"items": [], "target_type": tt, "q": query}

            cols = {
                r[0]
                for r in conn.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = :table
                        """
                    ),
                    {"table": table},
                ).fetchall()
            }
            code_expr = "ou.code" if "code" in cols else "NULL"
            parent_expr = "ou.parent_unit_id" if "parent_unit_id" in cols else "NULL"
            active_expr = "ou.is_active" if "is_active" in cols else "TRUE"

            rows = conn.execute(
                text(
                    f"""
                    SELECT
                        ou.unit_id AS target_id,
                        COALESCE(ou.name, 'org unit') AS label,
                        COALESCE({code_expr}::text, '') AS subtitle,
                        jsonb_build_object(
                            'parent_unit_id', {parent_expr},
                            'is_active', {active_expr}
                        ) AS metadata
                    FROM public.{table} ou
                    WHERE (
                        :empty_q
                        OR lower(COALESCE(ou.name, '')) LIKE :like
                        OR CAST(ou.unit_id AS text) LIKE :like
                    )
                    ORDER BY ou.unit_id
                    LIMIT :limit
                    """
                ),
                {"like": like, "limit": limit, "empty_q": not query},
            ).mappings().all()

    items = [
        {
            "target_type": tt,
            "target_id": int(r["target_id"]),
            "label": r.get("label"),
            "subtitle": r.get("subtitle"),
            "metadata": dict(r["metadata"]) if r.get("metadata") is not None else {},
        }
        for r in rows
    ]
    return {"items": items, "target_type": tt, "q": query, "limit": limit}
