# FILE: app/org_scope/resolver.py
from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.org_scope.types import DepartmentGroup


def parse_org_group_id(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 1 else None


def parse_org_unit_id(raw: Any) -> Optional[int]:
    return parse_org_group_id(raw)


def task_effective_owner_unit_sql(
    *,
    task_alias: str = "t",
    regular_task_alias: str = "rt",
) -> str:
    return f"""
        COALESCE(
            NULLIF(to_jsonb({task_alias})->>'owner_unit_id','')::int,
            NULLIF(to_jsonb({task_alias})->>'org_unit_id','')::int,
            NULLIF(to_jsonb({task_alias})->>'unit_id','')::int,
            NULLIF(to_jsonb({regular_task_alias})->>'owner_unit_id','')::int,
            NULLIF(to_jsonb({regular_task_alias})->>'org_unit_id','')::int,
            NULLIF(to_jsonb({regular_task_alias})->>'unit_id','')::int
        )
    """.strip()


def resolve_group_id_for_unit(
    conn: Connection,
    *,
    unit_id: int,
) -> Optional[int]:
    row = conn.execute(
        text(
            """
            SELECT group_id
            FROM public.org_units
            WHERE unit_id = :unit_id
            LIMIT 1
            """
        ),
        {"unit_id": int(unit_id)},
    ).mappings().first()
    if not row:
        return None
    raw = row.get("group_id")
    if raw is None:
        return None
    try:
        gid = int(raw)
    except (TypeError, ValueError):
        return None
    return gid if gid >= 1 else None


def resolve_subtree_unit_ids(
    conn: Connection,
    *,
    root_unit_id: int,
    include_inactive: bool = False,
) -> List[int]:
    active_filter = "" if include_inactive else "AND COALESCE(child.is_active, TRUE) = TRUE"
    rows = conn.execute(
        text(
            f"""
            WITH RECURSIVE org_scope_subtree AS (
                SELECT ou.unit_id
                FROM public.org_units ou
                WHERE ou.unit_id = :root_unit_id

                UNION ALL

                SELECT child.unit_id
                FROM public.org_units child
                JOIN org_scope_subtree s ON s.unit_id = child.parent_unit_id
                WHERE TRUE
                  {active_filter}
            )
            SELECT unit_id
            FROM org_scope_subtree
            ORDER BY unit_id
            """
        ),
        {"root_unit_id": int(root_unit_id)},
    ).mappings().all()
    out: List[int] = []
    for row in rows:
        try:
            out.append(int(row["unit_id"]))
        except (TypeError, ValueError, KeyError):
            continue
    return out


def load_department_groups(
    conn: Connection,
    *,
    limit: int = 50,
    offset: int = 0,
) -> List[DepartmentGroup]:
    rows = conn.execute(
        text(
            """
            SELECT group_id, group_name
            FROM public.deps_group
            ORDER BY group_id
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": max(1, int(limit)), "offset": max(0, int(offset))},
    ).mappings().all()
    out: List[DepartmentGroup] = []
    for row in rows:
        try:
            gid = int(row["group_id"])
        except (TypeError, ValueError, KeyError):
            continue
        if gid < 1:
            continue
        name = str(row.get("group_name") or "").strip()
        out.append(DepartmentGroup(group_id=gid, group_name=name))
    return out


def validate_org_group_exists(
    conn: Connection,
    *,
    org_group_id: int,
) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.deps_group
            WHERE group_id = :group_id
            LIMIT 1
            """
        ),
        {"group_id": int(org_group_id)},
    ).first()
    return bool(row)
