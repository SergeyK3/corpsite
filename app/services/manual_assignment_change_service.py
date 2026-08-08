"""Transactional manual assignment successor command.

This narrow ADR-043/C2 command owns assignment lifecycle writes. Employee is
updated only as the projection of the one active assignment.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.directory_service import _insert_employee_event
from app.services.hr_event_registry import get_event_class
from app.services.security_audit_service import write_security_event


_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ManualAssignmentChangeError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ManualAssignmentChangeResult:
    employee_id: int
    person_id: int
    predecessor_assignment_id: int
    successor_assignment_id: int
    event_id: int
    audit_id: int
    already_applied: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _command_assignment_key(*, person_id: int, idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return f"manual-change:{int(person_id)}:{digest}"


def _error(message: str, code: str) -> ManualAssignmentChangeError:
    return ManualAssignmentChangeError(message, code=code)


def _load_replay(
    conn: Connection,
    *,
    employee: dict[str, Any],
    assignments: list[dict[str, Any]],
    assignment_key: str,
    expected_assignment_id: int,
    org_unit_id: int,
    position_id: int,
    start_date: date,
) -> ManualAssignmentChangeResult | None:
    matches = [row for row in assignments if row["assignment_key"] == assignment_key]
    if not matches:
        return None
    if len(matches) != 1:
        raise _error("Ambiguous idempotency identity.", "MANUAL_ASSIGNMENT_IDEMPOTENCY_CONFLICT")
    successor = matches[0]
    active_ids = [
        int(row["assignment_id"])
        for row in assignments
        if row["active_flag"] and row["lifecycle_status"] == "active"
    ]
    if active_ids != [int(successor["assignment_id"])]:
        raise _error(
            "Idempotent replay no longer has exactly one active successor.",
            "ACTIVE_ASSIGNMENT_CARDINALITY_INVALID",
        )
    if (
        int(successor["org_unit_id"]) != int(org_unit_id)
        or int(successor["position_id"]) != int(position_id)
        or successor["start_date"] != start_date
        or not successor["active_flag"]
        or successor["lifecycle_status"] != "active"
    ):
        raise _error(
            "Idempotency key belongs to a different or no longer current assignment.",
            "MANUAL_ASSIGNMENT_IDEMPOTENCY_CONFLICT",
        )
    predecessor = next(
        (row for row in assignments if row["assignment_id"] == int(expected_assignment_id)),
        None,
    )
    if (
        predecessor is None
        or predecessor["lifecycle_status"] != "closed"
        or predecessor["active_flag"]
        or predecessor["end_date"] != start_date - timedelta(days=1)
    ):
        raise _error(
            "Idempotent successor has no expected closed predecessor.",
            "MANUAL_ASSIGNMENT_IDEMPOTENCY_CONFLICT",
        )
    if (
        int(employee["org_unit_id"]) != int(org_unit_id)
        or int(employee["position_id"]) != int(position_id)
        or employee["date_from"] != start_date
        or not employee["is_active"]
    ):
        raise _error("Employee projection differs from successor.", "EMPLOYEE_ASSIGNMENT_PROJECTION_STALE")
    event_ids = conn.execute(
        text(
            """
            SELECT event_id FROM public.employee_events
            WHERE employee_id=:employee_id
              AND metadata->>'manual_assignment_key'=:assignment_key
            ORDER BY event_id
            """
        ),
        {"employee_id": employee["employee_id"], "assignment_key": assignment_key},
    ).scalars().all()
    audit_ids = conn.execute(
        text(
            """
            SELECT audit_id FROM public.security_audit_log
            WHERE target_employee_id=:employee_id
              AND metadata->>'manual_assignment_key'=:assignment_key
            ORDER BY audit_id
            """
        ),
        {"employee_id": employee["employee_id"], "assignment_key": assignment_key},
    ).scalars().all()
    if len(event_ids) != 1 or len(audit_ids) != 1:
        raise _error("Idempotent evidence is missing or ambiguous.", "MANUAL_ASSIGNMENT_IDEMPOTENCY_CONFLICT")
    return ManualAssignmentChangeResult(
        employee_id=int(employee["employee_id"]),
        person_id=int(employee["person_id"]),
        predecessor_assignment_id=int(expected_assignment_id),
        successor_assignment_id=int(successor["assignment_id"]),
        event_id=int(event_ids[0]),
        audit_id=int(audit_ids[0]),
        already_applied=True,
    )


def _change_employee_assignment_tx(
    conn: Connection,
    *,
    employee_id: int,
    expected_assignment_id: int,
    org_unit_id: int,
    position_id: int,
    start_date: date,
    actor_user_id: int,
    idempotency_key: str,
    comment: str | None,
) -> ManualAssignmentChangeResult:
    normalized_key = str(idempotency_key or "").strip()
    if not _IDEMPOTENCY_RE.fullmatch(normalized_key):
        raise _error(
            "idempotency_key must be 1-128 safe ASCII characters.",
            "MANUAL_ASSIGNMENT_IDEMPOTENCY_KEY_INVALID",
        )
    if not isinstance(start_date, date):
        raise _error("start_date is required.", "ASSIGNMENT_START_DATE_INVALID")

    employee_row = conn.execute(
        text(
            """
            SELECT employee_id, person_id, org_unit_id, position_id,
                   employment_rate, date_from, is_active
            FROM public.employees
            WHERE employee_id=:employee_id
            FOR UPDATE
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    if employee_row is None:
        raise _error("Employee not found.", "EMPLOYEE_NOT_FOUND")
    employee = dict(employee_row)
    if employee["person_id"] is None:
        raise _error("Employee is not linked to Person.", "EMPLOYEE_PERSON_LINK_REQUIRED")
    if not employee["is_active"]:
        raise _error("Employee is inactive.", "EMPLOYEE_INACTIVE")
    person_id = int(employee["person_id"])

    assignments = [
        dict(row)
        for row in conn.execute(
            text(
                """
                SELECT assignment_id, person_id, org_unit_id, position_id, department_id,
                       employment_type, rate, start_date, end_date, active_flag,
                       is_primary, lifecycle_status, assignment_key, source
                FROM public.person_assignments
                WHERE person_id=:person_id
                ORDER BY assignment_id
                FOR UPDATE
                """
            ),
            {"person_id": person_id},
        ).mappings()
    ]
    assignment_key = _command_assignment_key(
        person_id=person_id, idempotency_key=normalized_key
    )
    replay = _load_replay(
        conn,
        employee=employee,
        assignments=assignments,
        assignment_key=assignment_key,
        expected_assignment_id=int(expected_assignment_id),
        org_unit_id=int(org_unit_id),
        position_id=int(position_id),
        start_date=start_date,
    )
    if replay is not None:
        return replay

    active = [
        row
        for row in assignments
        if row["active_flag"] and row["lifecycle_status"] == "active"
    ]
    if len(active) != 1:
        raise _error(
            "Employee must have exactly one active assignment.",
            "ACTIVE_ASSIGNMENT_CARDINALITY_INVALID",
        )
    predecessor = active[0]
    if int(predecessor["assignment_id"]) != int(expected_assignment_id):
        raise _error(
            "Active assignment changed after command preparation.",
            "ACTIVE_ASSIGNMENT_STALE",
        )
    if not predecessor["is_primary"]:
        raise _error("Active assignment must be primary.", "ACTIVE_ASSIGNMENT_NOT_PRIMARY")
    if (
        int(predecessor["org_unit_id"]) == int(org_unit_id)
        and int(predecessor["position_id"]) == int(position_id)
    ):
        raise _error("Target assignment is unchanged.", "ASSIGNMENT_TARGET_UNCHANGED")
    if start_date <= predecessor["start_date"]:
        raise _error(
            "Successor start_date must be later than predecessor start_date.",
            "ASSIGNMENT_DATE_RANGE_INVALID",
        )

    for table_name, id_column, identity in (
        ("org_units", "unit_id", int(org_unit_id)),
        ("positions", "position_id", int(position_id)),
        ("users", "user_id", int(actor_user_id)),
    ):
        found = conn.execute(
            text(
                f"SELECT {id_column} FROM public.{table_name} "
                f"WHERE {id_column}=:identity FOR KEY SHARE"
            ),
            {"identity": identity},
        ).scalar_one_or_none()
        if found is None:
            raise _error(f"{table_name} reference not found.", "ASSIGNMENT_REFERENCE_NOT_FOUND")

    active_links = conn.execute(
        text(
            """
            SELECT link_id, assignment_id
            FROM public.employee_assignment_links
            WHERE employee_id=:employee_id AND link_status='active'
            ORDER BY link_id
            FOR UPDATE
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().all()
    if any(int(link["assignment_id"]) != int(expected_assignment_id) for link in active_links):
        raise _error(
            "Employee has an active link to another assignment.",
            "EMPLOYEE_ASSIGNMENT_LINK_CONFLICT",
        )

    predecessor_end_date = start_date - timedelta(days=1)
    closed = conn.execute(
        text(
            """
            UPDATE public.person_assignments
            SET lifecycle_status='closed', active_flag=FALSE,
                end_date=:end_date, updated_at=now()
            WHERE assignment_id=:assignment_id
              AND active_flag IS TRUE AND lifecycle_status='active'
            """
        ),
        {"assignment_id": int(expected_assignment_id), "end_date": predecessor_end_date},
    )
    if closed.rowcount != 1:
        raise _error("Predecessor was not closed.", "ACTIVE_ASSIGNMENT_STALE")

    successor_id = int(
        conn.execute(
            text(
                """
                INSERT INTO public.person_assignments (
                    person_id, org_unit_id, position_id, department_id,
                    employment_type, rate, start_date, end_date,
                    active_flag, is_primary, lifecycle_status, assignment_key, source
                ) VALUES (
                    :person_id, :org_unit_id, :position_id, :department_id,
                    :employment_type, :rate, :start_date, NULL,
                    TRUE, :is_primary, 'active', :assignment_key, 'transfer'
                )
                RETURNING assignment_id
                """
            ),
            {
                "person_id": person_id,
                "org_unit_id": int(org_unit_id),
                "position_id": int(position_id),
                "department_id": predecessor["department_id"],
                "employment_type": predecessor["employment_type"],
                "rate": predecessor["rate"],
                "start_date": start_date,
                "is_primary": bool(predecessor["is_primary"]),
                "assignment_key": assignment_key,
            },
        ).scalar_one()
    )

    if active_links:
        conn.execute(
            text(
                """
                UPDATE public.employee_assignment_links
                SET link_status='superseded', unenrolled_at=now(),
                    unenrolled_by_user_id=:actor_user_id
                WHERE employee_id=:employee_id
                  AND assignment_id=:assignment_id
                  AND link_status='active'
                """
            ),
            {
                "employee_id": int(employee_id),
                "assignment_id": int(expected_assignment_id),
                "actor_user_id": int(actor_user_id),
            },
        )
    conn.execute(
        text(
            """
            INSERT INTO public.employee_assignment_links (
                employee_id, assignment_id, link_status, enrolled_by_user_id
            ) VALUES (:employee_id, :assignment_id, 'active', :actor_user_id)
            """
        ),
        {
            "employee_id": int(employee_id),
            "assignment_id": successor_id,
            "actor_user_id": int(actor_user_id),
        },
    )

    conn.execute(
        text(
            """
            UPDATE public.employees
            SET org_unit_id=:org_unit_id, position_id=:position_id,
                employment_rate=:rate, date_from=:start_date, date_to=NULL,
                is_active=TRUE, operational_status='active', updated_at=now()
            WHERE employee_id=:employee_id
            """
        ),
        {
            "employee_id": int(employee_id),
            "org_unit_id": int(org_unit_id),
            "position_id": int(position_id),
            "rate": predecessor["rate"],
            "start_date": start_date,
        },
    )
    if int(predecessor["org_unit_id"]) != int(org_unit_id):
        conn.execute(
            text("UPDATE public.users SET unit_id=:unit_id WHERE employee_id=:employee_id"),
            {"unit_id": int(org_unit_id), "employee_id": int(employee_id)},
        )

    event_type = (
        "TRANSFER"
        if int(predecessor["org_unit_id"]) != int(org_unit_id)
        else "POSITION_CHANGE"
    )
    event = _insert_employee_event(
        conn,
        employee_id=int(employee_id),
        event_type=event_type,
        event_class=get_event_class(event_type),
        lifecycle_status="APPROVED",
        metadata={
            "source": "manual_assignment_change_service",
            "manual_assignment_key": assignment_key,
            "predecessor_assignment_id": int(expected_assignment_id),
            "successor_assignment_id": successor_id,
        },
        effective_date=start_date,
        from_org_unit_id=int(predecessor["org_unit_id"]),
        from_position_id=int(predecessor["position_id"]),
        from_rate=float(predecessor["rate"]),
        to_org_unit_id=int(org_unit_id),
        to_position_id=int(position_id),
        to_rate=float(predecessor["rate"]),
        order_ref=None,
        comment=(comment or "").strip() or "Manual assignment change",
        created_by=int(actor_user_id),
    )
    audit_id = write_security_event(
        event_type="ACCESS_CHANGED",
        actor_user_id=int(actor_user_id),
        target_person_id=person_id,
        target_employee_id=int(employee_id),
        metadata={
            "action": "manual_assignment_changed",
            "manual_assignment_key": assignment_key,
            "predecessor_assignment_id": int(expected_assignment_id),
            "successor_assignment_id": successor_id,
            "org_unit_id": int(org_unit_id),
            "position_id": int(position_id),
            "start_date": start_date.isoformat(),
        },
        conn=conn,
    )
    if audit_id is None:
        raise _error("Security audit write is required.", "ASSIGNMENT_AUDIT_WRITE_FAILED")

    active_after = conn.execute(
        text(
            """
            SELECT assignment_id FROM public.person_assignments
            WHERE person_id=:person_id
              AND active_flag IS TRUE AND lifecycle_status='active'
            ORDER BY assignment_id
            FOR UPDATE
            """
        ),
        {"person_id": person_id},
    ).scalars().all()
    if active_after != [successor_id]:
        raise _error(
            "Postcondition failed: expected exactly one active successor.",
            "ACTIVE_ASSIGNMENT_POSTCONDITION_FAILED",
        )

    return ManualAssignmentChangeResult(
        employee_id=int(employee_id),
        person_id=person_id,
        predecessor_assignment_id=int(expected_assignment_id),
        successor_assignment_id=successor_id,
        event_id=int(event["event_id"]),
        audit_id=int(audit_id),
        already_applied=False,
    )


def change_employee_assignment(
    *,
    employee_id: int,
    expected_assignment_id: int,
    org_unit_id: int,
    position_id: int,
    start_date: date,
    actor_user_id: int,
    idempotency_key: str,
    comment: str | None = None,
    conn: Connection | None = None,
) -> ManualAssignmentChangeResult:
    """Close one predecessor and create one successor atomically.

    Without conn the service owns the transaction. A supplied connection is
    protected by a savepoint, so a caught exception cannot leave partial
    service writes in the caller-owned transaction.
    """
    kwargs = {
        "employee_id": employee_id,
        "expected_assignment_id": expected_assignment_id,
        "org_unit_id": org_unit_id,
        "position_id": position_id,
        "start_date": start_date,
        "actor_user_id": actor_user_id,
        "idempotency_key": idempotency_key,
        "comment": comment,
    }
    if conn is None:
        with engine.begin() as owned_conn:
            return _change_employee_assignment_tx(owned_conn, **kwargs)
    with conn.begin_nested():
        return _change_employee_assignment_tx(conn, **kwargs)
