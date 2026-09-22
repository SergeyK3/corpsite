"""Read-only projections for the employee account-access lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import text

from app.db.engine import engine


class EmployeeAccessReadError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_for_employee(conn, employee_id: int) -> Dict[str, Any]:
    employee = conn.execute(
        text("""
            SELECT employee_id, person_id, is_active
            FROM public.employees
            WHERE employee_id = :employee_id
            LIMIT 1
        """),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    if employee is None:
        raise EmployeeAccessReadError("EMPLOYEE_NOT_FOUND", "Employee not found.")
    return dict(employee)


def _users_for_employee(conn, employee_id: int) -> list[Dict[str, Any]]:
    rows = conn.execute(
        text("""
            SELECT user_id, is_active, must_change_password, locked_at,
                   locked_until, locked_reason, token_version
            FROM public.users
            WHERE employee_id = :employee_id
            ORDER BY user_id
        """),
        {"employee_id": int(employee_id)},
    ).mappings().all()
    return [dict(row) for row in rows]


def _linkage(employee: Dict[str, Any], users: list[Dict[str, Any]]) -> Dict[str, Any]:
    person_id = employee.get("person_id")
    if person_id is None:
        return {"state": "PERSON_MISSING", "has_user": False, "user": None}
    if not users:
        return {"state": "USER_MISSING", "has_user": False, "user": None}
    if len(users) != 1:
        return {"state": "USER_AMBIGUOUS", "has_user": True, "user": None}
    return {"state": "RESOLVED", "has_user": True, "user": users[0]}


def _has_active_assignment(conn, person_id: int | None) -> bool:
    if person_id is None:
        return False
    return bool(conn.execute(text("""
        SELECT 1 FROM public.person_assignments
        WHERE person_id=:person_id AND active_flag IS TRUE AND lifecycle_status='active'
        LIMIT 1
    """), {"person_id": int(person_id)}).scalar_one_or_none())


def _locked_state(user: Dict[str, Any]) -> bool:
    locked_at = user.get("locked_at")
    if locked_at is None:
        return False
    locked_until = user.get("locked_until")
    if locked_until is None:
        return True
    if getattr(locked_until, "tzinfo", None) is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return _now() < locked_until


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def get_employee_access_state(employee_id: int) -> Dict[str, Any]:
    """Return the safe state projection or a controlled linkage conflict."""
    with engine.connect() as conn:
        employee = _row_for_employee(conn, employee_id)
        users = _users_for_employee(conn, employee_id)
        linkage = _linkage(employee, users)
        if linkage["state"] != "RESOLVED":
            raise EmployeeAccessReadError(linkage["state"], "Employee/User linkage is not unambiguous.")
        user = linkage["user"]
        assert user is not None
        active_assignment = _has_active_assignment(conn, employee.get("person_id"))
    # The present schema has one common lock record.  Do not imply that it
    # distinguishes manual from automatic blocks before WP-ACCESS-004.
    lock_active = _locked_state(user)
    return {
        "employee_id": int(employee["employee_id"]),
        "person_id": int(employee["person_id"]),
        "user_id": int(user["user_id"]),
        "has_linked_user": True,
        "employee_is_active": bool(employee["is_active"]),
        "is_active": bool(user["is_active"]),
        "must_change_password": bool(user.get("must_change_password") or False),
        "lock_active": lock_active,
        "lock_reason": str(user["locked_reason"]) if user.get("locked_reason") is not None else None,
        "automatic_lock_active": lock_active and str(user.get("locked_reason") or "") == "brute_force",
        "locked_until": _iso(user.get("locked_until")),
        "token_version": int(user.get("token_version") or 1),
        "has_active_assignment": active_assignment,
        "generated_at": _now().isoformat(),
    }


def _count(conn, sql: str, params: Dict[str, Any]) -> int:
    return int(conn.execute(text(sql), params).scalar_one())


def _table_exists(conn, table: str) -> bool:
    return bool(conn.execute(text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='public' AND table_name=:table LIMIT 1
    """), {"table": table}).scalar_one_or_none())


def _source_available(conn, table: str) -> bool:
    """False means that the source cannot be safely used for a projection."""
    try:
        return _table_exists(conn, table)
    except Exception:
        return False


def _unavailable(counts: Dict[str, Any], statuses: Dict[str, str], warnings: list[str], key: str) -> None:
    if key == "active_direct_grants":
        counts["active_direct_grants_by_target_type"] = {
            "USER": None, "EMPLOYEE": None, "PERSON": None, "ASSIGNMENT": None,
        }
    else:
        counts[key] = None
    statuses[key] = "unavailable"
    warning = f"DEPENDENCY_SOURCE_UNAVAILABLE:{key}"
    if warning not in warnings:
        warnings.append(warning)


def _checked_count(conn, *, table: str, key: str, sql: str, params: Dict[str, Any], counts: Dict[str, Any], statuses: Dict[str, str], warnings: list[str]) -> None:
    if not _source_available(conn, table):
        _unavailable(counts, statuses, warnings, key)
        return
    try:
        counts[key] = _count(conn, sql, params)
        statuses[key] = "available"
    except Exception:
        _unavailable(counts, statuses, warnings, key)


def _preview_counts(conn, user_id: int | None, employee_id: int, person_id: int | None, warnings: list[str]) -> Dict[str, Any]:
    empty = {
        "unfinished_personal_tasks": None,
        "active_personal_approvals": None,
        "active_incoming_document_assignments": None,
        "pending_notifications_deliveries": None,
        "active_direct_grants_by_target_type": {"USER": None, "EMPLOYEE": None, "PERSON": None, "ASSIGNMENT": None},
        "dependency_status": {},
    }
    statuses = empty["dependency_status"]
    if user_id is None:
        for key in ("unfinished_personal_tasks", "active_personal_approvals", "active_incoming_document_assignments", "pending_notifications_deliveries", "active_direct_grants"):
            _unavailable(empty, statuses, warnings, key)
        return empty
    params = {"user_id": int(user_id), "employee_id": int(employee_id), "person_id": person_id}
    # Checklist items are the only current task model with explicit personal
    # assignee_user_id.  Role-assigned tasks are deliberately excluded.
    _checked_count(conn, table="employee_onboarding_checklist_items", key="unfinished_personal_tasks", sql="""
            SELECT COUNT(*) FROM public.employee_onboarding_checklist_items
            WHERE assignee_user_id=:user_id
              AND lower(COALESCE(status, '')) NOT IN ('completed', 'cancelled', 'skipped')
        """, params=params, counts=empty, statuses=statuses, warnings=warnings)
    _checked_count(conn, table="tasks", key="active_personal_approvals", sql="""
            SELECT COUNT(*) FROM public.tasks t
            JOIN public.task_statuses s ON s.status_id=t.status_id
            WHERE t.approver_user_id=:user_id AND COALESCE(s.is_terminal, FALSE)=FALSE
        """, params=params, counts=empty, statuses=statuses, warnings=warnings)
    _checked_count(conn, table="incoming_document_assignments", key="active_incoming_document_assignments", sql="""
            SELECT COUNT(*) FROM public.incoming_document_assignments
            WHERE assignee_user_id=:user_id AND completed_at IS NULL AND cancelled_at IS NULL
        """, params=params, counts=empty, statuses=statuses, warnings=warnings)
    notification_sources = (
        ("notifications", "SELECT COUNT(*) FROM public.notifications WHERE recipient_user_id=:user_id AND status='PENDING'"),
        ("task_event_deliveries", "SELECT COUNT(*) FROM public.task_event_deliveries WHERE user_id=:user_id AND status='PENDING'"),
        ("employee_onboarding_notification_deliveries", "SELECT COUNT(*) FROM public.employee_onboarding_notification_deliveries WHERE user_id=:user_id AND status='PENDING'"),
    )
    pending: int | None = 0
    for table, sql in notification_sources:
        if not _source_available(conn, table):
            pending = None
            break
        try:
            assert pending is not None
            pending += _count(conn, sql, params)
        except Exception:
            pending = None
            break
    if pending is None:
        _unavailable(empty, statuses, warnings, "pending_notifications_deliveries")
    else:
        empty["pending_notifications_deliveries"] = pending
        statuses["pending_notifications_deliveries"] = "available"
    assignment_ids: list[int] = []
    assignments_available = _source_available(conn, "person_assignments")
    if person_id is not None and assignments_available:
        try:
            assignment_ids = [int(v) for v in conn.execute(text("SELECT assignment_id FROM public.person_assignments WHERE person_id=:person_id"), params).scalars()]
        except Exception:
            assignments_available = False
    targets = {"USER": [int(user_id)], "EMPLOYEE": [int(employee_id)], "PERSON": [int(person_id)] if person_id is not None else [], "ASSIGNMENT": assignment_ids}
    grants_available = assignments_available and _source_available(conn, "access_grants")
    if not grants_available:
        _unavailable(empty, statuses, warnings, "active_direct_grants")
    else:
        statuses["active_direct_grants"] = "available"
    for target_type, ids in targets.items():
        if not grants_available:
            continue
        if not ids:
            empty["active_direct_grants_by_target_type"][target_type] = 0
            continue
        try:
            empty["active_direct_grants_by_target_type"][target_type] = _count(conn, """
                SELECT COUNT(*) FROM public.access_grants
                WHERE target_type=:target_type AND target_id = ANY(:ids)
                  AND active_flag IS TRUE AND starts_at <= statement_timestamp()
                  AND (ends_at IS NULL OR ends_at > statement_timestamp())
            """, {"target_type": target_type, "ids": ids})
        except Exception:
            _unavailable(empty, statuses, warnings, "active_direct_grants")
            break
    return empty


def get_employee_termination_preview(employee_id: int) -> Dict[str, Any]:
    """Return a read-only, aggregate-only preview; linkage conflicts are warnings."""
    with engine.connect() as conn:
        employee = _row_for_employee(conn, employee_id)
        users = _users_for_employee(conn, employee_id)
        linkage = _linkage(employee, users)
        user = linkage["user"]
        user_id = int(user["user_id"]) if user is not None else None
        person_id = int(employee["person_id"]) if employee.get("person_id") is not None else None
        warnings: list[str] = []
        if linkage["state"] != "RESOLVED":
            warnings.append(f"LINKAGE_{linkage['state']}")
        counts = _preview_counts(conn, user_id, int(employee_id), person_id, warnings)
        active_assignment = _has_active_assignment(conn, person_id)
        applied_termination: bool | None = None
        if _source_available(conn, "employee_events"):
            try:
                applied_termination = bool(conn.execute(text("""
                SELECT 1 FROM public.employee_events
                WHERE employee_id=:employee_id AND event_type='TERMINATION'
                  AND lifecycle_status='APPROVED' AND order_id IS NOT NULL
                LIMIT 1
                """), {"employee_id": int(employee_id)}).scalar_one_or_none())
            except Exception:
                warnings.append("DEPENDENCY_SOURCE_UNAVAILABLE:approved_termination_event")
        else:
            warnings.append("DEPENDENCY_SOURCE_UNAVAILABLE:approved_termination_event")
        grant_counts = counts["active_direct_grants_by_target_type"].values()
        if any(value is not None and int(value) > 0 for value in grant_counts):
            warnings.append("ACTIVE_DIRECT_GRANTS_PRESENT")
        if counts["unfinished_personal_tasks"] or counts["active_personal_approvals"] or counts["active_incoming_document_assignments"]:
            warnings.append("ACTIONABLE_PERSONAL_DEPENDENCIES_PRESENT")
    return {
        "employee_id": int(employee["employee_id"]),
        "person_id": person_id,
        "user_id": user_id,
        "linkage_state": linkage["state"],
        "has_linked_user": bool(linkage["has_user"]),
        "employee_is_active": bool(employee["is_active"]),
        "has_active_assignment": active_assignment,
        "has_applied_approved_termination_event": applied_termination,
        "counts": counts,
        "warnings": warnings,
        "generated_at": _now().isoformat(),
    }
