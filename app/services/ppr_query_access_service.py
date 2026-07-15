"""RBAC + visibility gates for PPR query API (R7)."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.db.engine import engine as default_engine
from app.directory.rbac import compute_scope, require_personnel_visibility_or_403
from app.security.personnel_admin_guard import evaluate_personnel_admin_access
from app.services.directory_service import get_employee


class PprQueryAccessDeniedError(PermissionError):
    """Raised when RBAC or visibility denies PPR read."""


def _is_org_wide_reader(user_ctx: dict[str, Any], scope: dict[str, Any]) -> bool:
    if scope.get("privileged"):
        return True
    return evaluate_personnel_admin_access(user_ctx)


def _employee_ids_for_person(conn: Connection, person_id: int) -> list[int]:
    rows = conn.execute(
        text(
            """
            SELECT employee_id
            FROM public.employees
            WHERE person_id = :person_id
            ORDER BY employee_id ASC
            """
        ),
        {"person_id": int(person_id)},
    ).scalars().all()
    return [int(row) for row in rows]


def _employee_visible_in_scope(
    *,
    employee_id: int,
    scope_unit_id: int | None,
    scope_unit_ids: list[int] | None,
) -> bool:
    try:
        get_employee(
            scope_unit_id=scope_unit_id,
            scope_unit_ids=scope_unit_ids,
            employee_id=str(employee_id),
        )
        return True
    except LookupError:
        return False


def assert_ppr_read_allowed_for_employee(
    user_ctx: dict[str, Any],
    employee_id: int,
    *,
    db_engine: Engine | None = None,
) -> None:
    """RBAC + visibility for transitional employee-scoped PPR reads."""
    uid = int(user_ctx["user_id"])
    scope = compute_scope(uid, user_ctx, include_inactive=True)
    require_personnel_visibility_or_403(user_ctx, scope)
    if _is_org_wide_reader(user_ctx, scope):
        return
    visible = _employee_visible_in_scope(
        employee_id=employee_id,
        scope_unit_id=scope.get("scope_unit_id"),
        scope_unit_ids=scope.get("scope_unit_ids"),
    )
    if not visible:
        raise HTTPException(status_code=404, detail="Employee not found.")


def assert_ppr_read_allowed_for_person(
    user_ctx: dict[str, Any],
    person_id: int,
    *,
    resolved_employee_id: int | None = None,
    db_engine: Engine | None = None,
) -> None:
    """RBAC + visibility for canonical person-scoped PPR reads."""
    uid = int(user_ctx["user_id"])
    scope = compute_scope(uid, user_ctx, include_inactive=True)
    require_personnel_visibility_or_403(user_ctx, scope)
    if _is_org_wide_reader(user_ctx, scope):
        return

    db = db_engine or default_engine
    with db.connect() as conn:
        employee_ids = _employee_ids_for_person(conn, person_id)

    if resolved_employee_id is not None and resolved_employee_id not in employee_ids:
        employee_ids = [resolved_employee_id, *employee_ids]

    if not employee_ids:
        raise HTTPException(status_code=404, detail="Person not found.")

    for employee_id in employee_ids:
        if _employee_visible_in_scope(
            employee_id=employee_id,
            scope_unit_id=scope.get("scope_unit_id"),
            scope_unit_ids=scope.get("scope_unit_ids"),
        ):
            return

    raise HTTPException(status_code=404, detail="Person not found.")


def include_sensitive_identity_fields(user_ctx: dict[str, Any]) -> bool:
    """Personnel admin / privileged users may receive full IIN in PPR read responses."""
    uid = int(user_ctx["user_id"])
    scope = compute_scope(uid, user_ctx)
    return _is_org_wide_reader(user_ctx, scope)
