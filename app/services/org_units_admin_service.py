# FILE: app/services/org_units_admin_service.py
"""Sysadmin CRUD for org_units with dependency checks and audit."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.db.engine import engine
from app.services.org_units_service import OrgUnit, OrgUnitsService
from app.services.security_audit_service import write_security_event

_ORG_UNITS = OrgUnitsService(engine)

def _column_exists(conn: Connection, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table AND column_name = :column
            LIMIT 1
            """
        ),
        {"table": table, "column": column},
    ).first()
    return row is not None


def _active_filter_sql(conn: Connection, table: str) -> str:
    if _column_exists(conn, table, "active_flag"):
        return "AND COALESCE(active_flag, true) = true"
    if _column_exists(conn, table, "is_active"):
        return "AND COALESCE(is_active, true) = true"
    if _column_exists(conn, table, "revoked_at"):
        return "AND revoked_at IS NULL"
    return ""


def _child_unit_ids(conn: Connection, unit_id: int) -> List[int]:
    rows = conn.execute(
        text("SELECT unit_id FROM public.org_units WHERE parent_unit_id = :uid ORDER BY unit_id"),
        {"uid": int(unit_id)},
    ).scalars().all()
    return [int(row) for row in rows]


def _apply_subtree_child_dependency_filter(
    dependencies: Dict[str, int],
    *,
    unit_id: int,
    subtree_unit_ids: Optional[Set[int]],
    conn: Connection,
) -> Dict[str, int]:
    filtered = dict(dependencies)
    if not subtree_unit_ids or int(filtered.get("child_org_units", 0)) <= 0:
        return filtered
    child_ids = _child_unit_ids(conn, unit_id)
    external_children = [cid for cid in child_ids if cid not in subtree_unit_ids]
    if external_children:
        filtered["child_org_units"] = len(external_children)
    else:
        filtered["child_org_units"] = 0
    return filtered


def check_org_unit_dependencies(
    unit_id: int,
    *,
    db_engine: Engine = engine,
    subtree_unit_ids: Optional[Set[int]] = None,
) -> OrgUnitDependencySummary:
    deps: Dict[str, int] = {}
    static_queries = {
        "child_org_units": "SELECT COUNT(*)::int FROM public.org_units WHERE parent_unit_id = :uid",
        "employees": "SELECT COUNT(*)::int FROM public.employees WHERE org_unit_id = :uid",
        "users": "SELECT COUNT(*)::int FROM public.users WHERE unit_id = :uid",
        "regular_tasks": "SELECT COUNT(*)::int FROM public.regular_tasks WHERE owner_unit_id = :uid",
        "org_unit_aliases": "SELECT COUNT(*)::int FROM public.org_unit_aliases WHERE org_unit_id = :uid",
        "org_unit_managers": "SELECT COUNT(*)::int FROM public.org_unit_managers WHERE unit_id = :uid",
        "user_org_units": "SELECT COUNT(*)::int FROM public.user_org_units WHERE unit_id = :uid",
        "org_unit_group_units": "SELECT COUNT(*)::int FROM public.org_unit_group_units WHERE unit_id = :uid",
        "org_unique_position": "SELECT COUNT(*)::int FROM public.org_unique_position WHERE org_unit_id = :uid",
        "legacy_position_mapping": "SELECT COUNT(*)::int FROM public.legacy_position_mapping WHERE org_unit_id = :uid",
        "permission_template_contour_rule": (
            "SELECT COUNT(*)::int FROM public.permission_template_contour_rule WHERE org_unit_id = :uid"
        ),
        "operational_order_draft_workspaces": (
            """
            SELECT COUNT(*)::int FROM public.operational_order_draft_workspaces
            WHERE organization_id = :uid OR submitting_org_unit_id = :uid
            """
        ),
        "operational_order_text_provenance": (
            "SELECT COUNT(*)::int FROM public.operational_order_text_provenance WHERE source_org_unit_id = :uid"
        ),
        "department_recoding": "SELECT COUNT(*)::int FROM public.department_recoding WHERE org_unit_id = :uid",
        "hr_change_events": "SELECT COUNT(*)::int FROM public.hr_change_events WHERE org_unit_id = :uid",
        "employee_events": (
            """
            SELECT COUNT(*)::int FROM public.employee_events
            WHERE from_org_unit_id = :uid OR to_org_unit_id = :uid
            """
        ),
        "personnel_order_items": (
            """
            SELECT COUNT(*)::int FROM public.personnel_order_items
            WHERE item_status <> 'VOIDED'
              AND (
                payload->>'org_unit_id' = :uid_text
                OR payload->>'to_org_unit_id' = :uid_text
                OR payload->>'from_org_unit_id' = :uid_text
              )
            """
        ),
    }

    table_by_key = {
        "child_org_units": "org_units",
        "active_employees": "employees",
        "personnel_order_items": "personnel_order_items",
        "operational_order_draft_workspaces": "operational_order_draft_workspaces",
        "operational_order_text_provenance": "operational_order_text_provenance",
        "permission_template_contour_rule": "permission_template_contour_rule",
        "legacy_position_mapping": "legacy_position_mapping",
        "org_unique_position": "org_unique_position",
        "org_unit_group_units": "org_unit_group_units",
        "org_unit_aliases": "org_unit_aliases",
        "org_unit_managers": "org_unit_managers",
        "user_org_units": "user_org_units",
        "department_recoding": "department_recoding",
        "hr_change_events": "hr_change_events",
        "employee_events": "employee_events",
    }

    with db_engine.begin() as conn:
        for key, sql in static_queries.items():
            table = table_by_key.get(key, key)
            if not _table_exists(conn, table):
                continue
            deps[key] = _count_query(conn, sql, unit_id=int(unit_id))

        if _table_exists(conn, "employees") and _column_exists(conn, "employees", "is_active"):
            deps["active_employees"] = _count_query(
                conn,
                """
                SELECT COUNT(*)::int FROM public.employees e
                WHERE e.org_unit_id = :uid AND COALESCE(e.is_active, true) = true
                """,
                unit_id=int(unit_id),
            )

        if _table_exists(conn, "person_assignments"):
            active_sql = _active_filter_sql(conn, "person_assignments")
            deps["person_assignments"] = _count_query(
                conn,
                f"""
                SELECT COUNT(*)::int FROM public.person_assignments
                WHERE org_unit_id = :uid {active_sql}
                """,
                unit_id=int(unit_id),
            )

        if _table_exists(conn, "personnel_visibility_assignments"):
            active_sql = _active_filter_sql(conn, "personnel_visibility_assignments")
            deps["personnel_visibility_assignments"] = _count_query(
                conn,
                f"""
                SELECT COUNT(*)::int FROM public.personnel_visibility_assignments
                WHERE (target_department_id = :uid OR scope_department_id = :uid)
                {active_sql}
                """,
                unit_id=int(unit_id),
            )

        if _table_exists(conn, "access_grants"):
            active_sql = _active_filter_sql(conn, "access_grants")
            deps["access_grants"] = _count_query(
                conn,
                f"""
                SELECT COUNT(*)::int FROM public.access_grants
                WHERE (
                    (target_type = 'ORG_UNIT' AND target_id = :uid)
                    OR (scope_type = 'ORG_UNIT' AND scope_id = :uid)
                )
                {active_sql}
                """,
                unit_id=int(unit_id),
            )

        if subtree_unit_ids is not None:
            deps = _apply_subtree_child_dependency_filter(
                deps,
                unit_id=int(unit_id),
                subtree_unit_ids=subtree_unit_ids,
                conn=conn,
            )

    total = sum(int(v) for v in deps.values())
    return OrgUnitDependencySummary(can_delete=total == 0, dependencies=deps)


@dataclass(frozen=True)
class OrgUnitDependencySummary:
    can_delete: bool
    dependencies: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "can_delete": self.can_delete,
            "dependencies": dict(self.dependencies),
        }


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table
            LIMIT 1
            """
        ),
        {"table": table},
    ).first()
    return row is not None


def _count_query(conn: Connection, sql: str, *, unit_id: int) -> int:
    row = conn.execute(
        text(sql),
        {"uid": int(unit_id), "uid_text": str(int(unit_id))},
    ).scalar_one_or_none()
    return int(row or 0)


def _audit_org_unit_event(
    *,
    event_type: str,
    actor_user_id: int,
    org_unit_id: int,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    dependencies: Optional[Dict[str, int]] = None,
    conn: Optional[Connection] = None,
) -> None:
    metadata: Dict[str, Any] = {"org_unit_id": int(org_unit_id)}
    if before is not None:
        metadata["before"] = before
    if after is not None:
        metadata["after"] = after
    if reason:
        metadata["reason"] = reason
    if dependencies is not None:
        metadata["dependencies"] = dependencies
    try:
        write_security_event(
            event_type=event_type,
            actor_user_id=int(actor_user_id),
            metadata=metadata,
            conn=conn,
        )
    except Exception:
        pass


def _org_unit_to_dict(unit: OrgUnit) -> Dict[str, Any]:
    return {
        "unit_id": unit.unit_id,
        "id": unit.unit_id,
        "parent_unit_id": unit.parent_unit_id,
        "parent_id": unit.parent_unit_id,
        "name": unit.name,
        "code": unit.code,
        "group_id": unit.group_id,
        "is_active": unit.is_active,
        "status": "active" if unit.is_active else "inactive",
    }


def _find_duplicate_sibling(
    *,
    name: str,
    parent_unit_id: Optional[int],
    exclude_unit_id: Optional[int] = None,
    db_engine: Engine = engine,
) -> Optional[int]:
    sql = text(
        """
        SELECT unit_id
        FROM public.org_units
        WHERE lower(btrim(name)) = lower(btrim(:name))
          AND (
            (parent_unit_id IS NULL AND :parent_unit_id IS NULL)
            OR parent_unit_id = :parent_unit_id
          )
          AND (:exclude_unit_id IS NULL OR unit_id <> :exclude_unit_id)
        LIMIT 1
        """
    )
    with db_engine.begin() as conn:
        row = conn.execute(
            sql,
            {
                "name": name,
                "parent_unit_id": parent_unit_id,
                "exclude_unit_id": exclude_unit_id,
            },
        ).scalar_one_or_none()
    return int(row) if row is not None else None


def _validate_group_exists(group_id: int, *, db_engine: Engine = engine) -> None:
    with db_engine.begin() as conn:
        if not _table_exists(conn, "deps_group"):
            return
        row = conn.execute(
            text("SELECT 1 FROM public.deps_group WHERE group_id = :gid LIMIT 1"),
            {"gid": int(group_id)},
        ).first()
        if not row:
            raise LookupError(f"deps_group not found: group_id={group_id}")


def _resolve_group_inheritance(
    *,
    parent_unit_id: Optional[int],
    group_id: int,
) -> int:
    """Child inherits parent group when parent exists; root keeps explicit group."""
    if parent_unit_id is None:
        return int(group_id)
    parent = _ORG_UNITS.get_org_unit(unit_id=int(parent_unit_id), include_inactive=True)
    if parent is None:
        raise LookupError(f"parent org unit not found: parent_unit_id={parent_unit_id}")
    if parent.group_id is not None:
        return int(parent.group_id)
    return int(group_id)


def list_admin_org_units(
    *,
    q: Optional[str] = None,
    org_group_id: Optional[int] = None,
    parent_unit_id: Optional[int] = None,
    status: str = "all",
    roots_only: bool = False,
    without_employees: bool = False,
    deletable_only: bool = False,
    limit: int = 500,
    offset: int = 0,
    db_engine: Engine = engine,
) -> Dict[str, Any]:
    where_parts = ["TRUE"]
    params: Dict[str, Any] = {"limit": int(limit), "offset": int(offset)}

    if status == "active":
        where_parts.append("COALESCE(ou.is_active, true) = true")
    elif status == "inactive":
        where_parts.append("COALESCE(ou.is_active, true) = false")

    if org_group_id is not None:
        where_parts.append("ou.group_id = :org_group_id")
        params["org_group_id"] = int(org_group_id)

    if parent_unit_id is not None:
        where_parts.append("ou.parent_unit_id = :parent_unit_id")
        params["parent_unit_id"] = int(parent_unit_id)

    if roots_only:
        where_parts.append("ou.parent_unit_id IS NULL")

    search = (q or "").strip()
    if search:
        where_parts.append(
            "(ou.name ILIKE :q OR COALESCE(ou.code, '') ILIKE :q OR CAST(ou.unit_id AS TEXT) = :q_exact)"
        )
        params["q"] = f"%{search}%"
        params["q_exact"] = search

    if without_employees:
        where_parts.append(
            """
            NOT EXISTS (
                SELECT 1 FROM public.employees e
                WHERE e.org_unit_id = ou.unit_id
            )
            """
        )

    if deletable_only:
        where_parts.append(
            """
            NOT EXISTS (SELECT 1 FROM public.org_units c WHERE c.parent_unit_id = ou.unit_id)
            AND NOT EXISTS (SELECT 1 FROM public.employees e WHERE e.org_unit_id = ou.unit_id)
            AND NOT EXISTS (SELECT 1 FROM public.users u WHERE u.unit_id = ou.unit_id)
            AND NOT EXISTS (SELECT 1 FROM public.regular_tasks rt WHERE rt.owner_unit_id = ou.unit_id)
            """
        )

    where_sql = " AND ".join(where_parts)

    count_sql = text(
        f"""
        SELECT COUNT(*)::int AS total
        FROM public.org_units ou
        WHERE {where_sql}
        """
    )
    list_sql = text(
        f"""
        SELECT
            ou.unit_id,
            ou.parent_unit_id,
            ou.name,
            ou.code,
            ou.group_id,
            COALESCE(ou.is_active, true) AS is_active,
            p.name AS parent_name,
            g.name AS group_name,
            (
                SELECT COUNT(*)::int FROM public.org_units c
                WHERE c.parent_unit_id = ou.unit_id
            ) AS child_count,
            (
                SELECT COUNT(*)::int FROM public.employees e
                WHERE e.org_unit_id = ou.unit_id
                  AND COALESCE(e.is_active, true) = true
            ) AS active_employee_count
        FROM public.org_units ou
        LEFT JOIN public.org_units p ON p.unit_id = ou.parent_unit_id
        LEFT JOIN public.org_unit_groups g ON g.group_id = ou.group_id
        WHERE {where_sql}
        ORDER BY ou.name, ou.unit_id
        LIMIT :limit OFFSET :offset
        """
    )

    with db_engine.begin() as conn:
        total = int(conn.execute(count_sql, params).scalar_one())
        rows = conn.execute(list_sql, params).mappings().all()

    items: List[Dict[str, Any]] = []
    for r in rows:
        item = {
            "unit_id": int(r["unit_id"]),
            "id": int(r["unit_id"]),
            "parent_unit_id": int(r["parent_unit_id"]) if r["parent_unit_id"] is not None else None,
            "parent_id": int(r["parent_unit_id"]) if r["parent_unit_id"] is not None else None,
            "parent_name": r.get("parent_name"),
            "name": r["name"],
            "code": r.get("code"),
            "group_id": int(r["group_id"]) if r.get("group_id") is not None else None,
            "group_name": r.get("group_name"),
            "is_active": bool(r["is_active"]),
            "status": "active" if bool(r["is_active"]) else "inactive",
            "child_count": int(r["child_count"] or 0),
            "active_employee_count": int(r["active_employee_count"] or 0),
        }
        items.append(item)

    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_admin_org_unit(unit_id: int, *, db_engine: Engine = engine) -> Dict[str, Any]:
    sql = text(
        """
        SELECT
            ou.unit_id,
            ou.parent_unit_id,
            ou.name,
            ou.code,
            ou.group_id,
            COALESCE(ou.is_active, true) AS is_active,
            p.name AS parent_name,
            g.name AS group_name,
            (
                SELECT COUNT(*)::int FROM public.org_units c
                WHERE c.parent_unit_id = ou.unit_id
            ) AS child_count,
            (
                SELECT COUNT(*)::int FROM public.employees e
                WHERE e.org_unit_id = ou.unit_id
                  AND COALESCE(e.is_active, true) = true
            ) AS active_employee_count
        FROM public.org_units ou
        LEFT JOIN public.org_units p ON p.unit_id = ou.parent_unit_id
        LEFT JOIN public.org_unit_groups g ON g.group_id = ou.group_id
        WHERE ou.unit_id = :unit_id
        LIMIT 1
        """
    )
    with db_engine.begin() as conn:
        r = conn.execute(sql, {"unit_id": int(unit_id)}).mappings().first()
    if not r:
        raise LookupError(f"org unit not found: unit_id={unit_id}")

    deps = check_org_unit_dependencies(int(unit_id), db_engine=db_engine)
    return {
        "item": {
            "unit_id": int(r["unit_id"]),
            "id": int(r["unit_id"]),
            "parent_unit_id": int(r["parent_unit_id"]) if r["parent_unit_id"] is not None else None,
            "parent_id": int(r["parent_unit_id"]) if r["parent_unit_id"] is not None else None,
            "parent_name": r.get("parent_name"),
            "name": r["name"],
            "code": r.get("code"),
            "group_id": int(r["group_id"]) if r.get("group_id") is not None else None,
            "group_name": r.get("group_name"),
            "is_active": bool(r["is_active"]),
            "status": "active" if bool(r["is_active"]) else "inactive",
            "child_count": int(r["child_count"] or 0),
            "active_employee_count": int(r["active_employee_count"] or 0),
            "can_delete": deps.can_delete,
        },
        "dependencies": deps.to_dict(),
    }


def create_admin_org_unit(
    *,
    actor_user_id: int,
    name: str,
    parent_unit_id: Optional[int] = None,
    group_id: int,
    code: Optional[str] = None,
    is_active: bool = True,
    allow_duplicate: bool = False,
    db_engine: Engine = engine,
) -> Dict[str, Any]:
    nm = (name or "").strip()
    if not nm:
        raise ValueError("name must not be empty")

    _validate_group_exists(int(group_id), db_engine=db_engine)
    resolved_group = _resolve_group_inheritance(
        parent_unit_id=parent_unit_id,
        group_id=int(group_id),
    )

    dup_id = _find_duplicate_sibling(
        name=nm,
        parent_unit_id=parent_unit_id,
        db_engine=db_engine,
    )
    if dup_id is not None and not allow_duplicate:
        raise ValueError(
            f"duplicate org unit name under same parent: existing unit_id={dup_id}"
        )

    unit = _ORG_UNITS.create_org_unit(
        name=nm,
        parent_unit_id=parent_unit_id,
        group_id=resolved_group,
        code=code,
        is_active=bool(is_active),
    )
    after = _org_unit_to_dict(unit)
    _audit_org_unit_event(
        event_type="ORG_UNIT_CREATED",
        actor_user_id=int(actor_user_id),
        org_unit_id=unit.unit_id,
        after=after,
    )
    return {"item": after}


def update_admin_org_unit(
    *,
    actor_user_id: int,
    unit_id: int,
    name: Optional[str] = None,
    code: Optional[str] = None,
    group_id: Optional[int] = None,
    parent_unit_id: Optional[int] = ...,  # type: ignore[assignment]
    is_active: Optional[bool] = None,
    allow_duplicate: bool = False,
    db_engine: Engine = engine,
) -> Dict[str, Any]:
    current = _ORG_UNITS.get_org_unit(unit_id=int(unit_id), include_inactive=True)
    if current is None:
        raise LookupError(f"org unit not found: unit_id={unit_id}")

    before = _org_unit_to_dict(current)
    updated = current

    if name is not None:
        nm = name.strip()
        if not nm:
            raise ValueError("name must not be empty")
        dup_id = _find_duplicate_sibling(
            name=nm,
            parent_unit_id=updated.parent_unit_id,
            exclude_unit_id=int(unit_id),
            db_engine=db_engine,
        )
        if dup_id is not None and not allow_duplicate:
            raise ValueError(
                f"duplicate org unit name under same parent: existing unit_id={dup_id}"
            )
        updated = _ORG_UNITS.rename_org_unit(unit_id=int(unit_id), new_name=nm)

    if code is not None:
        updated = _ORG_UNITS.update_org_unit_code(unit_id=int(unit_id), code=code)

    target_parent = updated.parent_unit_id if parent_unit_id is ... else parent_unit_id
    target_group = updated.group_id if group_id is None else int(group_id)

    if parent_unit_id is not ...:
        if target_group is not None:
            _validate_group_exists(int(target_group), db_engine=db_engine)
        resolved_group = _resolve_group_inheritance(
            parent_unit_id=target_parent,
            group_id=int(target_group or 0),
        )
        if resolved_group != (updated.group_id or 0):
            updated = _ORG_UNITS.update_org_unit_group(
                unit_id=int(unit_id),
                group_id=resolved_group,
            )
        updated = _ORG_UNITS.move_org_unit(
            unit_id=int(unit_id),
            parent_unit_id=target_parent,
        )
    elif group_id is not None:
        _validate_group_exists(int(group_id), db_engine=db_engine)
        resolved_group = _resolve_group_inheritance(
            parent_unit_id=updated.parent_unit_id,
            group_id=int(group_id),
        )
        updated = _ORG_UNITS.update_org_unit_group(
            unit_id=int(unit_id),
            group_id=resolved_group,
        )

    if is_active is not None:
        if bool(is_active):
            if updated.parent_unit_id is not None:
                parent = _ORG_UNITS.get_org_unit(
                    unit_id=int(updated.parent_unit_id),
                    include_inactive=True,
                )
                if parent is not None and not parent.is_active:
                    raise ValueError("cannot activate org unit: parent is inactive")
            updated = _ORG_UNITS.activate_org_unit(unit_id=int(unit_id))
        else:
            updated = _ORG_UNITS.deactivate_org_unit(unit_id=int(unit_id))

    after = _org_unit_to_dict(updated)
    _audit_org_unit_event(
        event_type="ORG_UNIT_UPDATED",
        actor_user_id=int(actor_user_id),
        org_unit_id=int(unit_id),
        before=before,
        after=after,
    )
    return {"item": after}


def activate_admin_org_unit(*, actor_user_id: int, unit_id: int) -> Dict[str, Any]:
    current = _ORG_UNITS.get_org_unit(unit_id=int(unit_id), include_inactive=True)
    if current is None:
        raise LookupError(f"org unit not found: unit_id={unit_id}")
    if current.parent_unit_id is not None:
        parent = _ORG_UNITS.get_org_unit(
            unit_id=int(current.parent_unit_id),
            include_inactive=True,
        )
        if parent is not None and not parent.is_active:
            raise ValueError("cannot activate org unit: parent is inactive")
    before = _org_unit_to_dict(current)
    updated = _ORG_UNITS.activate_org_unit(unit_id=int(unit_id))
    after = _org_unit_to_dict(updated)
    _audit_org_unit_event(
        event_type="ORG_UNIT_ACTIVATED",
        actor_user_id=int(actor_user_id),
        org_unit_id=int(unit_id),
        before=before,
        after=after,
    )
    return {"item": after}


def deactivate_admin_org_unit(*, actor_user_id: int, unit_id: int) -> Dict[str, Any]:
    current = _ORG_UNITS.get_org_unit(unit_id=int(unit_id), include_inactive=True)
    if current is None:
        raise LookupError(f"org unit not found: unit_id={unit_id}")
    before = _org_unit_to_dict(current)
    updated = _ORG_UNITS.deactivate_org_unit(unit_id=int(unit_id))
    after = _org_unit_to_dict(updated)
    _audit_org_unit_event(
        event_type="ORG_UNIT_DEACTIVATED",
        actor_user_id=int(actor_user_id),
        org_unit_id=int(unit_id),
        before=before,
        after=after,
    )
    return {"item": after}


class OrgUnitDeleteRejected(ValueError):
    def __init__(self, *, unit_id: int, dependencies: Dict[str, int]) -> None:
        self.unit_id = int(unit_id)
        self.dependencies = dict(dependencies)
        super().__init__(f"org unit {unit_id} has dependencies")


def delete_admin_org_unit(*, actor_user_id: int, unit_id: int) -> Dict[str, Any]:
    current = _ORG_UNITS.get_org_unit(unit_id=int(unit_id), include_inactive=True)
    if current is None:
        raise LookupError(f"org unit not found: unit_id={unit_id}")

    before = _org_unit_to_dict(current)
    deps = check_org_unit_dependencies(int(unit_id))
    if not deps.can_delete:
        _audit_org_unit_event(
            event_type="ORG_UNIT_DELETE_REJECTED",
            actor_user_id=int(actor_user_id),
            org_unit_id=int(unit_id),
            before=before,
            dependencies=deps.dependencies,
            reason="dependencies_present",
        )
        raise OrgUnitDeleteRejected(unit_id=int(unit_id), dependencies=deps.dependencies)

    _ORG_UNITS.delete_org_unit(unit_id=int(unit_id))
    _audit_org_unit_event(
        event_type="ORG_UNIT_DELETED",
        actor_user_id=int(actor_user_id),
        org_unit_id=int(unit_id),
        before=before,
    )
    return {"ok": True, "unit_id": int(unit_id)}


def _bulk_delete_failure_message(
    *,
    reason_code: str,
    dependencies: Optional[Dict[str, int]] = None,
    detail: Optional[str] = None,
) -> str:
    if reason_code == "NOT_FOUND":
        return "Подразделение не найдено"
    if reason_code == "ORG_UNIT_HAS_DEPENDENCIES":
        blocked = {k: v for k, v in (dependencies or {}).items() if int(v) > 0}
        if not blocked:
            return "Подразделение используется в системе"
        total = sum(int(v) for v in blocked.values())
        return f"Подразделение используется в системе ({total} связанных записей)"
    if reason_code == "SUBTREE_HAS_DEPENDENCIES":
        return "Удаление поддерева заблокировано: есть внешние зависимости"
    if reason_code == "VALIDATION_ERROR":
        return detail or "Удаление отклонено"
    return detail or "Удаление не выполнено"


def _fetch_subtree_units(
    conn: Connection,
    root_id: int,
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            WITH RECURSIVE subtree AS (
                SELECT
                    ou.unit_id,
                    ou.parent_unit_id,
                    ou.name,
                    0 AS depth
                FROM public.org_units ou
                WHERE ou.unit_id = :root_id
                UNION ALL
                SELECT
                    child.unit_id,
                    child.parent_unit_id,
                    child.name,
                    subtree.depth + 1 AS depth
                FROM public.org_units child
                JOIN subtree ON child.parent_unit_id = subtree.unit_id
            )
            SELECT unit_id, parent_unit_id, name, depth
            FROM subtree
            ORDER BY depth DESC, unit_id
            """
        ),
        {"root_id": int(root_id)},
    ).mappings().all()
    return [
        {
            "unit_id": int(row["unit_id"]),
            "parent_unit_id": int(row["parent_unit_id"]) if row["parent_unit_id"] is not None else None,
            "name": row["name"],
            "depth": int(row["depth"]),
        }
        for row in rows
    ]


def _nearest_selected_ancestor(
    conn: Connection,
    unit_id: int,
    selected: Set[int],
) -> Optional[int]:
    current = int(unit_id)
    seen: Set[int] = set()
    while current not in seen:
        seen.add(current)
        row = conn.execute(
            text("SELECT parent_unit_id FROM public.org_units WHERE unit_id = :uid LIMIT 1"),
            {"uid": current},
        ).scalar_one_or_none()
        if row is None:
            return None
        parent_id = int(row)
        if parent_id in selected:
            return parent_id
        current = parent_id
    return None


def _normalize_bulk_delete_roots(
    conn: Connection,
    unit_ids: List[int],
) -> Tuple[List[int], List[Tuple[int, int]]]:
    """Return effective roots and (covered_id, covering_root_id) pairs preserving input order."""
    selected = set(int(uid) for uid in unit_ids)
    if not selected:
        return [], []

    covered: List[Tuple[int, int]] = []
    roots: List[int] = []
    for uid in unit_ids:
        uid_int = int(uid)
        ancestor = _nearest_selected_ancestor(conn, uid_int, selected)
        if ancestor is not None and ancestor != uid_int:
            covered.append((uid_int, ancestor))
        elif uid_int not in {covered_id for covered_id, _ in covered}:
            if uid_int not in roots:
                roots.append(uid_int)
    return roots, covered


def _blocking_dependencies_for_subtree_unit(
    unit_id: int,
    *,
    subtree_unit_ids: Set[int],
    db_engine: Engine,
) -> Dict[str, int]:
    deps = check_org_unit_dependencies(
        int(unit_id),
        db_engine=db_engine,
        subtree_unit_ids=subtree_unit_ids,
    )
    return {k: int(v) for k, v in deps.dependencies.items() if int(v) > 0}


def _delete_org_unit_in_conn(conn: Connection, *, unit_id: int) -> None:
    uid = int(unit_id)
    deleted = conn.execute(
        text("DELETE FROM public.org_units WHERE unit_id = :unit_id"),
        {"unit_id": uid},
    )
    if not deleted.rowcount:
        raise LookupError(f"org unit not found: unit_id={uid}")


def preview_bulk_delete_admin_org_units(
    *,
    unit_ids: List[int],
    db_engine: Engine = engine,
) -> Dict[str, Any]:
    unique_ids = list(dict.fromkeys(int(raw_id) for raw_id in unit_ids))
    targets: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    not_found: List[int] = []

    with db_engine.connect() as conn:
        roots, covered = _normalize_bulk_delete_roots(conn, unique_ids)
        for covered_id, covering_root_id in covered:
            skipped.append({"id": int(covered_id), "covered_by": int(covering_root_id)})

        for root_id in roots:
            current = _ORG_UNITS.get_org_unit(unit_id=int(root_id), include_inactive=True)
            if current is None:
                not_found.append(int(root_id))
                continue
            subtree = _fetch_subtree_units(conn, int(root_id))
            descendants = [
                {"id": int(node["unit_id"]), "name": str(node["name"] or f"ID {node['unit_id']}")}
                for node in subtree
                if int(node["unit_id"]) != int(root_id)
            ]
            targets.append(
                {
                    "id": int(root_id),
                    "name": str(current.name or f"ID {root_id}"),
                    "descendants": descendants,
                    "subtree_size": len(subtree),
                }
            )

    return {
        "requested": len(unique_ids),
        "roots": targets,
        "skipped_as_covered": skipped,
        "not_found": not_found,
    }


def bulk_delete_admin_org_units(
    *,
    actor_user_id: int,
    unit_ids: List[int],
    db_engine: Engine = engine,
) -> Dict[str, Any]:
    unique_ids = list(dict.fromkeys(int(raw_id) for raw_id in unit_ids))
    failed: List[Dict[str, Any]] = []
    subtrees_to_delete: List[Tuple[int, str, List[Dict[str, Any]]]] = []

    with db_engine.connect() as conn:
        roots, covered = _normalize_bulk_delete_roots(conn, unique_ids)
        covered_ids = {int(covered_id) for covered_id, _ in covered}

        for uid in unique_ids:
            uid_int = int(uid)
            if uid_int in covered_ids or uid_int not in roots:
                continue
            if _ORG_UNITS.get_org_unit(unit_id=uid_int, include_inactive=True) is None:
                failed.append(
                    {
                        "id": uid_int,
                        "name": f"ID {uid_int}",
                        "reason_code": "NOT_FOUND",
                        "message": _bulk_delete_failure_message(reason_code="NOT_FOUND"),
                    }
                )

        for root_id in roots:
            current = _ORG_UNITS.get_org_unit(unit_id=int(root_id), include_inactive=True)
            if current is None:
                continue

            root_name = str(current.name or f"ID {root_id}")
            subtree = _fetch_subtree_units(conn, int(root_id))
            if not subtree:
                failed.append(
                    {
                        "id": int(root_id),
                        "name": root_name,
                        "reason_code": "NOT_FOUND",
                        "message": _bulk_delete_failure_message(reason_code="NOT_FOUND"),
                    }
                )
                continue

            subtree_ids = {int(node["unit_id"]) for node in subtree}
            blocked_units: List[Dict[str, Any]] = []
            for node in subtree:
                unit_id = int(node["unit_id"])
                blocked = _blocking_dependencies_for_subtree_unit(
                    unit_id,
                    subtree_unit_ids=subtree_ids,
                    db_engine=db_engine,
                )
                if blocked:
                    blocked_units.append(
                        {
                            "id": unit_id,
                            "name": str(node["name"] or f"ID {unit_id}"),
                            "dependencies": blocked,
                        }
                    )

            if blocked_units:
                before = _org_unit_to_dict(current)
                _audit_org_unit_event(
                    event_type="ORG_UNIT_DELETE_REJECTED",
                    actor_user_id=int(actor_user_id),
                    org_unit_id=int(root_id),
                    before=before,
                    dependencies=blocked_units[0]["dependencies"],
                    reason="dependencies_present",
                )
                failed.append(
                    {
                        "id": int(root_id),
                        "name": root_name,
                        "reason_code": "SUBTREE_HAS_DEPENDENCIES",
                        "message": _bulk_delete_failure_message(reason_code="SUBTREE_HAS_DEPENDENCIES"),
                        "blocked_units": blocked_units,
                    }
                )
                continue

            subtrees_to_delete.append((int(root_id), root_name, subtree))

    deleted_ids: List[int] = []
    if subtrees_to_delete:
        with db_engine.begin() as conn:
            for _root_id, _root_name, subtree in subtrees_to_delete:
                for node in subtree:
                    unit_id = int(node["unit_id"])
                    unit = _ORG_UNITS.get_org_unit(unit_id=unit_id, include_inactive=True)
                    before = _org_unit_to_dict(unit) if unit is not None else {
                        "unit_id": unit_id,
                        "id": unit_id,
                        "parent_unit_id": node["parent_unit_id"],
                        "parent_id": node["parent_unit_id"],
                        "name": node["name"],
                        "code": None,
                        "group_id": None,
                        "is_active": True,
                        "status": "active",
                    }
                    try:
                        _delete_org_unit_in_conn(conn, unit_id=unit_id)
                        _audit_org_unit_event(
                            event_type="ORG_UNIT_DELETED",
                            actor_user_id=int(actor_user_id),
                            org_unit_id=unit_id,
                            before=before,
                            conn=conn,
                        )
                        deleted_ids.append(unit_id)
                    except LookupError:
                        failed.append(
                            {
                                "id": unit_id,
                                "name": str(node["name"] or f"ID {unit_id}"),
                                "reason_code": "NOT_FOUND",
                                "message": _bulk_delete_failure_message(reason_code="NOT_FOUND"),
                            }
                        )
                    except Exception as exc:
                        failed.append(
                            {
                                "id": unit_id,
                                "name": str(node["name"] or f"ID {unit_id}"),
                                "reason_code": "VALIDATION_ERROR",
                                "message": _bulk_delete_failure_message(
                                    reason_code="VALIDATION_ERROR",
                                    detail=str(exc),
                                ),
                            }
                        )

    return {
        "deleted_ids": deleted_ids,
        "failed": failed,
        "requested": len(unique_ids),
    }
