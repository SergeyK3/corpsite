"""Verification-aware archival termination flow for incomplete historical records."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.directory_service import _insert_employee_event
from app.services.hr_event_registry import get_event_class
from app.services.hr_import_employee_binding_service import (
    BINDING_METHOD_IIN,
    BINDING_STATUS_BOUND,
    EmployeeBindingResult,
    persist_row_employee_binding,
)
from app.services.hr_import_roster_promotion_service import _insert_employee_identity


UNVERIFIED = "UNVERIFIED"
VERIFIED = "VERIFIED"


class TerminationVerificationError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ArchivedImportEmployee:
    row_id: int
    person_id: int
    employee_id: int
    termination_record_id: int
    created_person: bool
    created_employee: bool
    created_termination_record: bool


def _clean_name(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _parse_birth_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise TerminationVerificationError(
            "Import row contains an invalid birth_date.", code="IMPORT_BIRTH_DATE_INVALID"
        ) from exc


def _fio_components(full_name: str) -> tuple[str | None, str | None, str | None]:
    parts = full_name.split()
    return (
        parts[0] if parts else None,
        parts[1] if len(parts) > 1 else None,
        " ".join(parts[2:]) if len(parts) > 2 else None,
    )


def _load_import_row(conn: Connection, *, batch_id: int, row_id: int) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT row_id, batch_id, employee_id, normalized_payload
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id AND row_id = :row_id
            FOR UPDATE
            """
        ),
        {"batch_id": int(batch_id), "row_id": int(row_id)},
    ).mappings().first()
    if row is None:
        raise TerminationVerificationError("Import row not found.", code="IMPORT_ROW_NOT_FOUND")
    payload = row.get("normalized_payload")
    if not isinstance(payload, dict):
        payload = json.loads(str(payload or "{}"))
    return {**dict(row), "payload": payload}


def _normalized_record_ids(conn: Connection, *, batch_id: int, row_id: int) -> list[int]:
    return [
        int(value)
        for value in conn.execute(
            text(
                """
                SELECT normalized_record_id
                FROM public.hr_import_normalized_records
                WHERE batch_id = :batch_id AND row_id = :row_id
                ORDER BY normalized_record_id
                """
            ),
            {"batch_id": int(batch_id), "row_id": int(row_id)},
        ).scalars()
    ]


def _assert_reference(conn: Connection, *, org_unit_id: int, position_id: int) -> None:
    org = conn.execute(
        text("SELECT name FROM public.org_units WHERE unit_id=:id AND is_active IS TRUE"),
        {"id": int(org_unit_id)},
    ).scalar_one_or_none()
    if org is None:
        raise TerminationVerificationError("Active org unit not found.", code="ORG_UNIT_NOT_FOUND")
    pos = conn.execute(
        text("SELECT name FROM public.positions WHERE position_id=:id"), {"id": int(position_id)}
    ).scalar_one_or_none()
    if pos is None:
        raise TerminationVerificationError("Position not found.", code="POSITION_NOT_FOUND")


def _assert_no_active_assignment(conn: Connection, *, person_id: int) -> None:
    assignment_id = conn.execute(
        text(
            """
            SELECT assignment_id
            FROM public.person_assignments
            WHERE person_id = :person_id
              AND active_flag IS TRUE
              AND lifecycle_status <> 'voided'
            ORDER BY assignment_id
            LIMIT 1
            FOR UPDATE
            """
        ),
        {"person_id": int(person_id)},
    ).scalar_one_or_none()
    if assignment_id is not None:
        raise TerminationVerificationError(
            "Employee has an active assignment.", code="ACTIVE_ASSIGNMENT_EXISTS"
        )


def _get_or_create_person(
    conn: Connection, *, full_name: str, iin: str, birth_date: date | None, batch_id: int, row_id: int
) -> tuple[int, bool]:
    people = conn.execute(
        text(
            """
            SELECT person_id, full_name, birth_date
            FROM public.persons
            WHERE iin = :iin AND person_status <> 'merged'
            ORDER BY person_id
            FOR UPDATE
            """
        ),
        {"iin": iin},
    ).mappings().all()
    if len(people) > 1:
        raise TerminationVerificationError("Multiple Persons have this IIN.", code="PERSON_IIN_AMBIGUOUS")
    if people:
        person = people[0]
        if _clean_name(person.get("full_name")) != full_name:
            raise TerminationVerificationError("Person name differs from import.", code="PERSON_NAME_CONFLICT")
        if birth_date and person.get("birth_date") and person["birth_date"] != birth_date:
            raise TerminationVerificationError("Person birth date differs from import.", code="PERSON_BIRTH_DATE_CONFLICT")
        return int(person["person_id"]), False

    last_name, first_name, middle_name = _fio_components(full_name)
    person_id = conn.execute(
        text(
            """
            INSERT INTO public.persons (
                iin, full_name, last_name, first_name, middle_name, birth_date,
                match_key, person_status, source
            ) VALUES (
                :iin, :full_name, :last_name, :first_name, :middle_name, :birth_date,
                :match_key, 'active', 'enrollment'
            )
            RETURNING person_id
            """
        ),
        {
            "iin": iin,
            "full_name": full_name,
            "last_name": last_name,
            "first_name": first_name,
            "middle_name": middle_name,
            "birth_date": birth_date,
            "match_key": f"hr-import:{int(batch_id)}:row:{int(row_id)}",
        },
    ).scalar_one()
    return int(person_id), True


def _get_or_create_employee(
    conn: Connection,
    *,
    person_id: int,
    full_name: str,
    iin: str,
    org_unit_id: int,
    position_id: int,
    actor_user_id: int,
) -> tuple[int, bool]:
    rows = conn.execute(
        text(
            """
            SELECT e.employee_id, e.person_id, e.full_name, e.org_unit_id,
                   e.position_id, e.is_active, e.operational_status
            FROM public.employees e
            WHERE e.person_id = :person_id
               OR EXISTS (
                    SELECT 1 FROM public.employee_identities ei
                    WHERE ei.employee_id = e.employee_id
                      AND ei.identity_type = 'IIN'
                      AND ei.identity_value = :iin
                      AND ei.valid_to IS NULL
               )
            ORDER BY e.employee_id
            FOR UPDATE OF e
            """
        ),
        {"person_id": int(person_id), "iin": iin},
    ).mappings().all()
    if len(rows) > 1:
        raise TerminationVerificationError("Multiple Employees match this identity.", code="EMPLOYEE_IDENTITY_AMBIGUOUS")
    if rows:
        employee = rows[0]
        expected = (int(person_id), full_name, int(org_unit_id), int(position_id), False, "terminated")
        actual = (
            int(employee["person_id"]) if employee.get("person_id") is not None else None,
            _clean_name(employee.get("full_name")),
            int(employee["org_unit_id"]) if employee.get("org_unit_id") is not None else None,
            int(employee["position_id"]) if employee.get("position_id") is not None else None,
            bool(employee.get("is_active")),
            str(employee.get("operational_status") or ""),
        )
        if actual != expected:
            raise TerminationVerificationError(
                "Existing Employee does not match the requested archived state.",
                code="EMPLOYEE_STATE_CONFLICT",
            )
        return int(employee["employee_id"]), False

    employee_id = conn.execute(
        text(
            """
            INSERT INTO public.employees (
                person_id, full_name, org_unit_id, position_id, date_from, date_to,
                employment_rate, is_active, operational_status, enrollment_source,
                enrolled_at, enrolled_by_user_id, updated_at
            ) VALUES (
                :person_id, :full_name, :org_unit_id, :position_id, NULL, NULL,
                1.0, FALSE, 'terminated', 'enrollment', NOW(), :actor_user_id, NOW()
            )
            RETURNING employee_id
            """
        ),
        {
            "person_id": int(person_id),
            "full_name": full_name,
            "org_unit_id": int(org_unit_id),
            "position_id": int(position_id),
            "actor_user_id": int(actor_user_id),
        },
    ).scalar_one()
    return int(employee_id), True


def _append_audit(
    conn: Connection,
    *,
    termination_record_id: int,
    action: str,
    before_status: str | None,
    after_status: str,
    actor_user_id: int,
    details: dict[str, Any],
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.employee_termination_record_audit (
                termination_record_id, action, before_status, after_status,
                actor_user_id, details
            ) VALUES (
                :record_id, :action, :before_status, :after_status,
                :actor_user_id, CAST(:details AS JSONB)
            )
            """
        ),
        {
            "record_id": int(termination_record_id),
            "action": action,
            "before_status": before_status,
            "after_status": after_status,
            "actor_user_id": int(actor_user_id),
            "details": json.dumps(details, ensure_ascii=False),
        },
    )


def archive_import_employee_unverified(
    conn: Connection,
    *,
    batch_id: int,
    row_id: int,
    org_unit_id: int,
    position_id: int,
    actor_user_id: int,
) -> ArchivedImportEmployee:
    """Create/link one historical Employee without inventing termination facts."""
    row = _load_import_row(conn, batch_id=batch_id, row_id=row_id)
    payload = row["payload"]
    full_name = _clean_name(payload.get("full_name"))
    iin = "".join(ch for ch in str(payload.get("iin") or "") if ch.isdigit())
    if not full_name or len(iin) != 12:
        raise TerminationVerificationError(
            "Import row requires full_name and a 12-digit IIN.", code="IMPORT_IDENTITY_INVALID"
        )
    conn.execute(text("SELECT pg_advisory_xact_lock(65065, hashtext(:iin))"), {"iin": iin})
    _assert_reference(conn, org_unit_id=org_unit_id, position_id=position_id)
    person_id, created_person = _get_or_create_person(
        conn,
        full_name=full_name,
        iin=iin,
        birth_date=_parse_birth_date(payload.get("birth_date")),
        batch_id=batch_id,
        row_id=row_id,
    )
    _assert_no_active_assignment(conn, person_id=person_id)
    employee_id, created_employee = _get_or_create_employee(
        conn,
        person_id=person_id,
        full_name=full_name,
        iin=iin,
        org_unit_id=org_unit_id,
        position_id=position_id,
        actor_user_id=actor_user_id,
    )
    _insert_employee_identity(conn, employee_id=employee_id, iin=iin, created_by=actor_user_id)

    record_ids = _normalized_record_ids(conn, batch_id=batch_id, row_id=row_id)
    existing = conn.execute(
        text(
            """
            SELECT termination_record_id, verification_status, source_batch_id, source_row_id
            FROM public.employee_termination_records
            WHERE employee_id = :employee_id
            FOR UPDATE
            """
        ),
        {"employee_id": employee_id},
    ).mappings().first()
    created_record = False
    if existing is None:
        termination_record_id = int(
            conn.execute(
                text(
                    """
                    INSERT INTO public.employee_termination_records (
                        employee_id, verification_status, termination_date, order_number,
                        order_date, source_batch_id, source_row_id,
                        source_normalized_record_ids, created_by, updated_by
                    ) VALUES (
                        :employee_id, 'UNVERIFIED', NULL, NULL, NULL, :batch_id,
                        :row_id, :record_ids, :actor_user_id, :actor_user_id
                    )
                    RETURNING termination_record_id
                    """
                ),
                {
                    "employee_id": employee_id,
                    "batch_id": int(batch_id),
                    "row_id": int(row_id),
                    "record_ids": record_ids,
                    "actor_user_id": int(actor_user_id),
                },
            ).scalar_one()
        )
        created_record = True
        _append_audit(
            conn,
            termination_record_id=termination_record_id,
            action="CREATED_UNVERIFIED",
            before_status=None,
            after_status=UNVERIFIED,
            actor_user_id=actor_user_id,
            details={"batch_id": int(batch_id), "row_id": int(row_id), "normalized_record_ids": record_ids},
        )
    else:
        termination_record_id = int(existing["termination_record_id"])
        if (
            str(existing["verification_status"]) != UNVERIFIED
            or int(existing["source_batch_id"] or 0) != int(batch_id)
            or int(existing["source_row_id"] or 0) != int(row_id)
        ):
            raise TerminationVerificationError(
                "Existing termination record conflicts with import provenance.",
                code="TERMINATION_RECORD_CONFLICT",
            )

    persist_row_employee_binding(
        conn,
        int(row_id),
        EmployeeBindingResult(
            employee_id=employee_id,
            status=BINDING_STATUS_BOUND,
            method=BINDING_METHOD_IIN,
            reason="Archived Employee created from existing HR import row",
        ),
        force=True,
    )
    return ArchivedImportEmployee(
        row_id=int(row_id),
        person_id=person_id,
        employee_id=employee_id,
        termination_record_id=termination_record_id,
        created_person=created_person,
        created_employee=created_employee,
        created_termination_record=created_record,
    )


def verify_employee_termination(
    conn: Connection,
    *,
    employee_id: int,
    termination_date: date,
    order_number: str,
    order_date: date,
    actor_user_id: int,
) -> dict[str, Any]:
    if termination_date is None or order_date is None:
        raise TerminationVerificationError(
            "termination_date, order_number and order_date are required.",
            code="TERMINATION_FACTS_REQUIRED",
        )
    normalized_order_number = str(order_number or "").strip()
    if not normalized_order_number:
        raise TerminationVerificationError("order_number is required.", code="TERMINATION_FACTS_REQUIRED")
    employee = conn.execute(
        text(
            """
            SELECT employee_id, person_id, org_unit_id, position_id, employment_rate, is_active
            FROM public.employees WHERE employee_id=:employee_id FOR UPDATE
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    if employee is None:
        raise TerminationVerificationError("Employee not found.", code="EMPLOYEE_NOT_FOUND")
    if bool(employee.get("is_active")):
        raise TerminationVerificationError("Employee is active.", code="EMPLOYEE_STILL_ACTIVE")
    if employee.get("person_id") is not None:
        _assert_no_active_assignment(conn, person_id=int(employee["person_id"]))
    record = conn.execute(
        text(
            """
            SELECT * FROM public.employee_termination_records
            WHERE employee_id=:employee_id FOR UPDATE
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    if record is None:
        raise TerminationVerificationError(
            "Termination record not found.", code="TERMINATION_RECORD_NOT_FOUND"
        )
    if str(record["verification_status"]) == VERIFIED:
        same = (
            record.get("termination_date") == termination_date
            and str(record.get("order_number") or "") == normalized_order_number
            and record.get("order_date") == order_date
        )
        if same:
            return dict(record)
        raise TerminationVerificationError(
            "Termination is already verified with different facts.", code="TERMINATION_ALREADY_VERIFIED"
        )

    conn.execute(
        text(
            """
            UPDATE public.employees
            SET date_to=:termination_date, is_active=FALSE,
                operational_status='terminated', updated_at=NOW()
            WHERE employee_id=:employee_id
            """
        ),
        {"termination_date": termination_date, "employee_id": int(employee_id)},
    )
    event = _insert_employee_event(
        conn,
        employee_id=int(employee_id),
        event_type="TERMINATION",
        event_class=get_event_class("TERMINATION"),
        lifecycle_status="APPROVED",
        metadata={"termination_verification_status": VERIFIED},
        effective_date=termination_date,
        from_org_unit_id=int(employee["org_unit_id"]) if employee.get("org_unit_id") else None,
        from_position_id=int(employee["position_id"]) if employee.get("position_id") else None,
        from_rate=float(employee["employment_rate"]) if employee.get("employment_rate") is not None else None,
        to_org_unit_id=None,
        to_position_id=None,
        to_rate=None,
        order_ref=f"№ {normalized_order_number} от {order_date.isoformat()}",
        comment="Сведения об увольнении верифицированы кадровиком",
        created_by=int(actor_user_id),
    )
    updated = conn.execute(
        text(
            """
            UPDATE public.employee_termination_records
            SET verification_status='VERIFIED', termination_date=:termination_date,
                order_number=:order_number, order_date=:order_date,
                termination_event_id=:event_id, updated_by=:actor_user_id,
                updated_at=NOW(), verified_by=:actor_user_id, verified_at=NOW()
            WHERE termination_record_id=:record_id AND verification_status='UNVERIFIED'
            RETURNING *
            """
        ),
        {
            "termination_date": termination_date,
            "order_number": normalized_order_number,
            "order_date": order_date,
            "event_id": int(event["event_id"]),
            "actor_user_id": int(actor_user_id),
            "record_id": int(record["termination_record_id"]),
        },
    ).mappings().one()
    _append_audit(
        conn,
        termination_record_id=int(record["termination_record_id"]),
        action="VERIFIED",
        before_status=UNVERIFIED,
        after_status=VERIFIED,
        actor_user_id=actor_user_id,
        details={
            "termination_date": termination_date.isoformat(),
            "order_number": normalized_order_number,
            "order_date": order_date.isoformat(),
            "termination_event_id": int(event["event_id"]),
        },
    )
    return dict(updated)
