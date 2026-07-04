"""ADR-051 Phase 2.3 — Cabinet Access Resolver (read path only, no enforcement).

This module implements the Position → Cabinet → Permission Template resolution chain
introduced by ADR-050. It coexists with ``access_resolver_service`` (ADR-042 B3 grant
overlay) and does not replace any runtime authorization path in this phase.

Architecture (read path):
    legacy (org_unit_id, catalog_position_id)
        → org_unique_position
        → position_cabinet
        → permission_template
        → effective_permissions (ADR-053: access_role_id → access_roles.code; else role_id → roles.code)

Non-goals in Phase 2.3:
    - No JWT, /auth/me, login, or frontend changes
    - No person_assignments retarget
    - No automatic fallback to users.role_id or access_grants
    - No writes; missing data returns an empty resolution (never raises)
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine

DEFAULT_CLIENT_SCOPE_ID = 1

_REASON_TABLES_MISSING = "adr050_tables_missing"
_REASON_LEGACY_MAPPING_NOT_FOUND = "legacy_mapping_not_found"
_REASON_POSITION_LIQUIDATED = "position_liquidated"
_REASON_POSITION_CABINET_NOT_FOUND = "position_cabinet_not_found"
_REASON_PERMISSION_TEMPLATE_NOT_FOUND = "permission_template_not_found"
_REASON_PERMISSION_TEMPLATE_INACTIVE = "permission_template_inactive"
_REASON_POSITION_VACANT = "position_vacant"
_REASON_EMPLOYEE_NOT_FOUND = "employee_not_found"
_REASON_EMPLOYEE_STAFFING_INCOMPLETE = "employee_staffing_incomplete"
_REASON_STAFFING_KEYS_REQUIRED = "org_unit_id_and_catalog_position_id_required"


def _empty_position_cabinet_resolution(
    *,
    client_scope_id: int,
    org_unit_id: int,
    catalog_position_id: int,
    reason: str,
) -> Dict[str, Any]:
    return {
        "resolved": False,
        "client_scope_id": int(client_scope_id),
        "org_unit_id": int(org_unit_id),
        "catalog_position_id": int(catalog_position_id),
        "org_unique_position": None,
        "position_cabinet": None,
        "reason": reason,
    }


def _empty_permission_template_resolution(
    *,
    position_cabinet_id: int,
    reason: str,
) -> Dict[str, Any]:
    return {
        "resolved": False,
        "position_cabinet_id": int(position_cabinet_id),
        "permission_template": None,
        "reason": reason,
    }


def _empty_effective_permissions(
    *,
    employee_id: Optional[int],
    org_unit_id: Optional[int],
    catalog_position_id: Optional[int],
    reason: str,
) -> Dict[str, Any]:
    return {
        "resolved": False,
        "employee_id": int(employee_id) if employee_id is not None else None,
        "org_unit_id": int(org_unit_id) if org_unit_id is not None else None,
        "catalog_position_id": int(catalog_position_id) if catalog_position_id is not None else None,
        "org_unique_position": None,
        "position_cabinet": None,
        "permission_template": None,
        "effective_permissions": [],
        "reason": reason,
    }


def _table_exists(conn: Connection, table: str) -> bool:
    return (
        conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = :table
                LIMIT 1
                """
            ),
            {"table": table},
        ).first()
        is not None
    )


def _phase2_tables_available(conn: Connection) -> bool:
    required = (
        "org_unique_position",
        "position_cabinet",
        "permission_template",
        "legacy_position_mapping",
    )
    return all(_table_exists(conn, table) for table in required)


def _run_with_conn(conn: Optional[Connection], fn: Callable[[Connection], Dict[str, Any]]) -> Dict[str, Any]:
    if conn is not None:
        return fn(conn)
    with engine.connect() as owned:
        return fn(owned)


def _serialize_org_unique_position(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "org_unique_position_id": int(row["org_unique_position_id"]),
        "client_scope_id": int(row["client_scope_id"]),
        "org_unit_id": int(row["org_unit_id"]),
        "catalog_position_id": int(row["catalog_position_id"]),
        "lifecycle_status": str(row["lifecycle_status"]),
    }


def _serialize_position_cabinet(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row or row.get("position_cabinet_id") is None:
        return None
    return {
        "position_cabinet_id": int(row["position_cabinet_id"]),
        "org_unique_position_id": int(row["org_unique_position_id"]),
    }


def _serialize_permission_template(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "permission_template_id": int(row["permission_template_id"]),
        "position_cabinet_id": int(row["position_cabinet_id"]),
        "access_role_id": int(row["access_role_id"]) if row.get("access_role_id") is not None else None,
        "access_role_code": str(row["access_role_code"]) if row.get("access_role_code") is not None else None,
        "role_id": int(row["role_id"]) if row.get("role_id") is not None else None,
        "role_code": str(row["role_code"]) if row.get("role_code") is not None else None,
        "is_active": bool(row["is_active"]),
    }


def _expand_effective_permissions(template: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not template or not template.get("is_active"):
        return []

    access_role_code = template.get("access_role_code")
    if access_role_code:
        return [
            {
                "permission_code": str(access_role_code),
                "source": "permission_template_access_role",
                "access_role_id": template.get("access_role_id"),
            }
        ]

    role_code = template.get("role_code")
    if role_code:
        return [
            {
                "permission_code": str(role_code),
                "source": "permission_template_role",
                "role_id": template.get("role_id"),
            }
        ]

    return []


def _load_legacy_staffing_row(
    conn: Connection,
    *,
    client_scope_id: int,
    org_unit_id: int,
    catalog_position_id: int,
) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT
                lpm.legacy_position_mapping_id,
                lpm.client_scope_id,
                lpm.org_unit_id,
                lpm.catalog_position_id,
                lpm.org_unique_position_id,
                oup.lifecycle_status,
                pc.position_cabinet_id
            FROM public.legacy_position_mapping lpm
            JOIN public.org_unique_position oup
              ON oup.org_unique_position_id = lpm.org_unique_position_id
            LEFT JOIN public.position_cabinet pc
              ON pc.org_unique_position_id = oup.org_unique_position_id
            WHERE lpm.client_scope_id = :client_scope_id
              AND lpm.org_unit_id = :org_unit_id
              AND lpm.catalog_position_id = :catalog_position_id
            ORDER BY lpm.legacy_position_mapping_id
            LIMIT 1
            """
        ),
        {
            "client_scope_id": int(client_scope_id),
            "org_unit_id": int(org_unit_id),
            "catalog_position_id": int(catalog_position_id),
        },
    ).mappings().first()
    return dict(row) if row else None


def _load_permission_template_row(conn: Connection, *, position_cabinet_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT
                pt.permission_template_id,
                pt.position_cabinet_id,
                pt.access_role_id,
                pt.role_id,
                pt.is_active,
                ar.code AS access_role_code,
                r.code AS role_code
            FROM public.permission_template pt
            LEFT JOIN public.access_roles ar
              ON ar.access_role_id = pt.access_role_id
             AND ar.is_active IS TRUE
            LEFT JOIN public.roles r
              ON r.role_id = pt.role_id
            WHERE pt.position_cabinet_id = :position_cabinet_id
            ORDER BY pt.permission_template_id
            LIMIT 1
            """
        ),
        {"position_cabinet_id": int(position_cabinet_id)},
    ).mappings().first()
    return dict(row) if row else None


def _load_employee_staffing(conn: Connection, *, employee_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT
                e.employee_id,
                e.org_unit_id,
                e.position_id AS catalog_position_id
            FROM public.employees e
            WHERE e.employee_id = :employee_id
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    return dict(row) if row else None


def resolve_position_cabinet(
    *,
    org_unit_id: int,
    catalog_position_id: int,
    client_scope_id: int = DEFAULT_CLIENT_SCOPE_ID,
    conn: Optional[Connection] = None,
) -> Dict[str, Any]:
    """Resolve org-unique Position and its Position Cabinet for a legacy staffing pair."""

    def _resolve(active_conn: Connection) -> Dict[str, Any]:
        if not _phase2_tables_available(active_conn):
            return _empty_position_cabinet_resolution(
                client_scope_id=client_scope_id,
                org_unit_id=org_unit_id,
                catalog_position_id=catalog_position_id,
                reason=_REASON_TABLES_MISSING,
            )

        row = _load_legacy_staffing_row(
            active_conn,
            client_scope_id=client_scope_id,
            org_unit_id=org_unit_id,
            catalog_position_id=catalog_position_id,
        )
        if row is None:
            return _empty_position_cabinet_resolution(
                client_scope_id=client_scope_id,
                org_unit_id=org_unit_id,
                catalog_position_id=catalog_position_id,
                reason=_REASON_LEGACY_MAPPING_NOT_FOUND,
            )

        lifecycle_status = str(row["lifecycle_status"])
        if lifecycle_status == "liquidated":
            return _empty_position_cabinet_resolution(
                client_scope_id=client_scope_id,
                org_unit_id=org_unit_id,
                catalog_position_id=catalog_position_id,
                reason=_REASON_POSITION_LIQUIDATED,
            )

        org_unique_position = _serialize_org_unique_position(row)
        position_cabinet = _serialize_position_cabinet(row)
        if position_cabinet is None:
            return {
                "resolved": False,
                "client_scope_id": int(client_scope_id),
                "org_unit_id": int(org_unit_id),
                "catalog_position_id": int(catalog_position_id),
                "org_unique_position": org_unique_position,
                "position_cabinet": None,
                "reason": _REASON_POSITION_CABINET_NOT_FOUND,
            }

        return {
            "resolved": True,
            "client_scope_id": int(client_scope_id),
            "org_unit_id": int(org_unit_id),
            "catalog_position_id": int(catalog_position_id),
            "org_unique_position": org_unique_position,
            "position_cabinet": position_cabinet,
            "reason": None,
        }

    return _run_with_conn(conn, _resolve)


def resolve_permission_template(
    *,
    position_cabinet_id: int,
    conn: Optional[Connection] = None,
) -> Dict[str, Any]:
    """Resolve the Permission Template bound to a Position Cabinet."""

    def _resolve(active_conn: Connection) -> Dict[str, Any]:
        if not _phase2_tables_available(active_conn):
            return _empty_permission_template_resolution(
                position_cabinet_id=position_cabinet_id,
                reason=_REASON_TABLES_MISSING,
            )

        row = _load_permission_template_row(active_conn, position_cabinet_id=position_cabinet_id)
        if row is None:
            return _empty_permission_template_resolution(
                position_cabinet_id=position_cabinet_id,
                reason=_REASON_PERMISSION_TEMPLATE_NOT_FOUND,
            )

        template = _serialize_permission_template(row)
        if not template["is_active"]:
            return {
                "resolved": False,
                "position_cabinet_id": int(position_cabinet_id),
                "permission_template": template,
                "reason": _REASON_PERMISSION_TEMPLATE_INACTIVE,
            }

        return {
            "resolved": True,
            "position_cabinet_id": int(position_cabinet_id),
            "permission_template": template,
            "reason": None,
        }

    return _run_with_conn(conn, _resolve)


def resolve_effective_permissions(
    *,
    employee_id: Optional[int] = None,
    org_unit_id: Optional[int] = None,
    catalog_position_id: Optional[int] = None,
    client_scope_id: int = DEFAULT_CLIENT_SCOPE_ID,
    conn: Optional[Connection] = None,
) -> Dict[str, Any]:
    """Resolve the full Cabinet chain and transitional effective permissions."""

    def _resolve(active_conn: Connection) -> Dict[str, Any]:
        resolved_org_unit_id = org_unit_id
        resolved_catalog_position_id = catalog_position_id

        if employee_id is not None:
            employee = _load_employee_staffing(active_conn, employee_id=int(employee_id))
            if employee is None:
                return _empty_effective_permissions(
                    employee_id=employee_id,
                    org_unit_id=resolved_org_unit_id,
                    catalog_position_id=resolved_catalog_position_id,
                    reason=_REASON_EMPLOYEE_NOT_FOUND,
                )
            if employee.get("org_unit_id") is None or employee.get("catalog_position_id") is None:
                return _empty_effective_permissions(
                    employee_id=employee_id,
                    org_unit_id=resolved_org_unit_id,
                    catalog_position_id=resolved_catalog_position_id,
                    reason=_REASON_EMPLOYEE_STAFFING_INCOMPLETE,
                )
            resolved_org_unit_id = int(employee["org_unit_id"])
            resolved_catalog_position_id = int(employee["catalog_position_id"])

        if resolved_org_unit_id is None or resolved_catalog_position_id is None:
            return _empty_effective_permissions(
                employee_id=employee_id,
                org_unit_id=resolved_org_unit_id,
                catalog_position_id=resolved_catalog_position_id,
                reason=_REASON_STAFFING_KEYS_REQUIRED,
            )

        cabinet_resolution = resolve_position_cabinet(
            org_unit_id=int(resolved_org_unit_id),
            catalog_position_id=int(resolved_catalog_position_id),
            client_scope_id=client_scope_id,
            conn=active_conn,
        )
        if not cabinet_resolution["resolved"]:
            return _empty_effective_permissions(
                employee_id=employee_id,
                org_unit_id=int(resolved_org_unit_id),
                catalog_position_id=int(resolved_catalog_position_id),
                reason=str(cabinet_resolution["reason"]),
            )

        org_unique_position = cabinet_resolution["org_unique_position"]
        position_cabinet = cabinet_resolution["position_cabinet"]
        assert org_unique_position is not None
        assert position_cabinet is not None

        if org_unique_position["lifecycle_status"] == "vacant":
            return {
                "resolved": False,
                "employee_id": int(employee_id) if employee_id is not None else None,
                "org_unit_id": int(resolved_org_unit_id),
                "catalog_position_id": int(resolved_catalog_position_id),
                "org_unique_position": org_unique_position,
                "position_cabinet": position_cabinet,
                "permission_template": None,
                "effective_permissions": [],
                "reason": _REASON_POSITION_VACANT,
            }

        template_resolution = resolve_permission_template(
            position_cabinet_id=int(position_cabinet["position_cabinet_id"]),
            conn=active_conn,
        )
        permission_template = template_resolution.get("permission_template")
        if not template_resolution["resolved"]:
            return {
                "resolved": False,
                "employee_id": int(employee_id) if employee_id is not None else None,
                "org_unit_id": int(resolved_org_unit_id),
                "catalog_position_id": int(resolved_catalog_position_id),
                "org_unique_position": org_unique_position,
                "position_cabinet": position_cabinet,
                "permission_template": permission_template,
                "effective_permissions": [],
                "reason": str(template_resolution["reason"]),
            }

        effective_permissions = _expand_effective_permissions(permission_template)
        return {
            "resolved": True,
            "employee_id": int(employee_id) if employee_id is not None else None,
            "org_unit_id": int(resolved_org_unit_id),
            "catalog_position_id": int(resolved_catalog_position_id),
            "org_unique_position": org_unique_position,
            "position_cabinet": position_cabinet,
            "permission_template": permission_template,
            "effective_permissions": effective_permissions,
            "reason": None,
        }

    return _run_with_conn(conn, _resolve)
