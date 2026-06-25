"""ADR-039 Phase 3I — enroll operational employee from normalized HR import record."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.department_recoding_service import lookup_recoding
from app.services.hr_import_analytics_service import (
    _build_roster_department_index,
    _norm_person_name,
    _resolve_declaration_department,
)
from app.services.hr_import_employee_binding_service import (
    BINDING_METHOD_IIN,
    BINDING_STATUS_BOUND,
    EmployeeBindingResult,
    _digits_only,
    _lookup_employees_by_iin,
    _parse_payload,
    persist_row_employee_binding,
    propagate_employee_id_to_normalized_records,
)
from app.services.hr_import_normalized_record_service import (
    NormalizedRecordNotFoundError,
    _fetch_normalized_record_row,
    _serialize_normalized_record,
)
from app.services.hr_import_roster_promotion_service import _insert_employee_identity
from app.services.hr_event_registry import get_event_class
from app.services.operational_contact_service import ensure_operational_contact_for_employee
from app.services.security_audit_service import write_security_event

EVENT_TYPE_ENROLLED_FROM_IMPORT = "EMPLOYEE_ENROLLED_FROM_IMPORT"

OUTCOME_READY = "ready"
OUTCOME_CREATED = "created"
OUTCOME_CONFLICT = "conflict"
OUTCOME_BLOCKED = "blocked"

CONFLICT_IIN_ALREADY_EXISTS = "IIN_ALREADY_EXISTS"
CONFLICT_IIN_MULTIPLE_MATCH = "IIN_MULTIPLE_MATCH"


class EnrollEmployeeError(Exception):
    def __init__(self, message: str, *, code: str = "blocked") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass
class EnrollEmployeeRequest:
    dry_run: bool = True
    full_name: Optional[str] = None
    org_unit_id: Optional[int] = None
    position_id: Optional[int] = None
    date_from: Optional[date] = None
    employment_rate: Optional[float] = None
    link_same_iin_in_batch: bool = True


@dataclass
class EnrollEmployeeResult:
    dry_run: bool
    outcome: str
    created: bool = False
    matched_by: str = "iin"
    employee_id: Optional[int] = None
    contact_id: Optional[int] = None
    contact_created: bool = False
    linked_records_count: int = 0
    linked_record_ids: list[int] = field(default_factory=list)
    linked_row_ids: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    preview: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    conflict: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "outcome": self.outcome,
            "created": self.created,
            "matched_by": self.matched_by,
            "employee_id": self.employee_id,
            "contact_id": self.contact_id,
            "contact_created": self.contact_created,
            "linked_records_count": self.linked_records_count,
            "linked_record_ids": list(self.linked_record_ids),
            "linked_row_ids": list(self.linked_row_ids),
            "warnings": list(self.warnings),
            "preview": dict(self.preview),
            "provenance": dict(self.provenance),
            "conflict": dict(self.conflict) if self.conflict else None,
        }


def _load_batch_meta(conn: Connection, batch_id: int) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT batch_id, file_name, source_type, imported_at
            FROM public.hr_import_batches
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().first()
    if row is None:
        raise EnrollEmployeeError(f"batch_id={batch_id} not found", code="blocked")
    return dict(row)


def _load_row_payload(conn: Connection, row_id: int) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT
                row_id,
                batch_id,
                employee_id,
                source_sheet,
                source_row_number,
                normalized_payload,
                review_status
            FROM public.hr_import_rows
            WHERE row_id = :row_id
            """
        ),
        {"row_id": row_id},
    ).mappings().first()
    if row is None:
        raise EnrollEmployeeError(f"import row {row_id} not found", code="blocked")
    payload = _parse_payload(row["normalized_payload"])
    return {
        "row_id": int(row["row_id"]),
        "batch_id": int(row["batch_id"]),
        "employee_id": int(row["employee_id"]) if row.get("employee_id") else None,
        "source_sheet": str(row.get("source_sheet") or ""),
        "source_row_number": int(row["source_row_number"]) if row.get("source_row_number") else None,
        "payload": payload,
    }


def _org_unit_name(conn: Connection, org_unit_id: Optional[int]) -> str:
    if org_unit_id is None:
        return ""
    row = conn.execute(
        text("SELECT name FROM public.org_units WHERE unit_id = :unit_id"),
        {"unit_id": org_unit_id},
    ).scalar()
    return str(row or "").strip()


def _position_name(conn: Connection, position_id: Optional[int]) -> str:
    if position_id is None:
        return ""
    row = conn.execute(
        text("SELECT name FROM public.positions WHERE position_id = :position_id"),
        {"position_id": position_id},
    ).scalar()
    return str(row or "").strip()


def _employee_exists(conn: Connection, employee_id: int) -> bool:
    return (
        conn.execute(
            text("SELECT 1 FROM public.employees WHERE employee_id = :employee_id"),
            {"employee_id": employee_id},
        ).first()
        is not None
    )


def _employee_profile(conn: Connection, employee_id: int) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT
                e.employee_id,
                e.full_name,
                e.org_unit_id,
                ou.name AS org_unit_name,
                e.position_id,
                p.name AS position_name
            FROM public.employees e
            LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id
            LEFT JOIN public.positions p ON p.position_id = e.position_id
            WHERE e.employee_id = :employee_id
            """
        ),
        {"employee_id": employee_id},
    ).mappings().first()
    if row is None:
        return {"employee_id": employee_id}
    return {
        "employee_id": int(row["employee_id"]),
        "full_name": str(row.get("full_name") or "").strip(),
        "org_unit_id": int(row["org_unit_id"]) if row.get("org_unit_id") else None,
        "org_unit_name": str(row.get("org_unit_name") or "").strip(),
        "position_id": int(row["position_id"]) if row.get("position_id") else None,
        "position_name": str(row.get("position_name") or "").strip(),
    }


def _load_batch_row_items(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    db_rows = conn.execute(
        text(
            """
            SELECT row_id, normalized_payload
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
            ORDER BY row_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()
    items: list[dict[str, Any]] = []
    for db_row in db_rows:
        payload = _parse_payload(db_row["normalized_payload"])
        items.append(
            {
                "row_id": int(db_row["row_id"]),
                "full_name": str(payload.get("full_name") or "").strip(),
                "iin": _digits_only(str(payload.get("iin") or "")),
                "department": str(payload.get("department") or "").strip(),
                "position_raw": str(payload.get("position_raw") or "").strip(),
                "payload": payload,
            }
        )
    return items


def _resolve_department_hint(conn: Connection, batch_id: int, *, iin: str, full_name: str) -> Optional[dict[str, Any]]:
    items = _load_batch_row_items(conn, batch_id)
    roster_by_iin_name, roster_by_iin, roster_by_name = _build_roster_department_index(items)
    department = _resolve_declaration_department(
        {"iin": iin, "full_name": full_name, "department": ""},
        by_iin_name=roster_by_iin_name,
        by_iin=roster_by_iin,
        by_name=roster_by_name,
    )
    for item in items:
        if item["row_id"] and item.get("department"):
            if iin and item["iin"] == iin:
                department = department or item["department"]
            elif full_name and _norm_person_name(item["full_name"]) == _norm_person_name(full_name):
                department = department or item["department"]
    if not department:
        return None
    rec = lookup_recoding(conn, department)
    if rec and rec.get("org_unit_id"):
        return {
            "value": department,
            "org_unit_id": int(rec["org_unit_id"]),
            "org_unit_name": str(rec.get("org_unit_name") or department),
            "source": "import" if department else "roster_index",
            "confidence": "exact" if rec else "inferred",
        }
    return {
        "value": department,
        "org_unit_id": None,
        "org_unit_name": "",
        "source": "import",
        "confidence": "inferred",
    }


def _resolve_position_hint(row_payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    position_raw = str(row_payload.get("position_raw") or "").strip()
    if not position_raw:
        return None
    return {"value": position_raw, "source": "import"}


def _find_batch_rows_by_iin(conn: Connection, *, batch_id: int, iin_digits: str) -> list[int]:
    rows = conn.execute(
        text(
            """
            SELECT row_id
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
              AND regexp_replace(COALESCE(normalized_payload->>'iin', ''), '[^0-9]', '', 'g') = :iin
            ORDER BY row_id
            """
        ),
        {"batch_id": batch_id, "iin": iin_digits},
    ).fetchall()
    return [int(row[0]) for row in rows if row and row[0]]


def _find_batch_normalized_records_by_iin(
    conn: Connection,
    *,
    batch_id: int,
    iin_digits: str,
) -> list[int]:
    rows = conn.execute(
        text(
            """
            SELECT nr.normalized_record_id
            FROM public.hr_import_normalized_records nr
            JOIN public.hr_import_rows r ON r.row_id = nr.row_id
            WHERE nr.batch_id = :batch_id
              AND regexp_replace(COALESCE(r.normalized_payload->>'iin', ''), '[^0-9]', '', 'g') = :iin
              AND nr.promoted_document_id IS NULL
            ORDER BY nr.normalized_record_id
            """
        ),
        {"batch_id": batch_id, "iin": iin_digits},
    ).fetchall()
    return [int(row[0]) for row in rows if row and row[0]]


def _check_iin_conflicts(conn: Connection, iin_digits: str) -> Optional[dict[str, Any]]:
    employee_ids = _lookup_employees_by_iin(conn, iin_digits)
    if len(employee_ids) > 1:
        profiles = [_employee_profile(conn, emp_id) for emp_id in employee_ids]
        return {
            "code": CONFLICT_IIN_MULTIPLE_MATCH,
            "candidate_employee_ids": employee_ids,
            "candidates": profiles,
            "message": f"Найдено несколько сотрудников с ИИН {iin_digits}",
        }
    if len(employee_ids) == 1:
        profile = _employee_profile(conn, employee_ids[0])
        return {
            "code": CONFLICT_IIN_ALREADY_EXISTS,
            "existing_employee_id": employee_ids[0],
            "existing_employee_name": profile.get("full_name"),
            "existing_org_unit_name": profile.get("org_unit_name"),
            "existing_position_name": profile.get("position_name"),
            "candidates": [profile],
            "message": f"Сотрудник с ИИН {iin_digits} уже существует",
        }
    return None


def _validate_record_eligible(
    conn: Connection,
    *,
    record_row: dict[str, Any],
    import_row: dict[str, Any],
) -> tuple[str, str]:
    review_status = str(record_row.get("review_status") or "")
    if review_status in {"promoted", "superseded"}:
        raise EnrollEmployeeError("normalized record is locked for enrollment", code="blocked")

    if import_row.get("employee_id"):
        raise EnrollEmployeeError("record is already linked to an employee", code="blocked")

    full_name = str(record_row.get("full_name") or import_row["payload"].get("full_name") or "").strip()
    iin_raw = str(record_row.get("row_iin") or record_row.get("iin") or import_row["payload"].get("iin") or "")
    iin_digits = _digits_only(iin_raw)
    if len(iin_digits) != 12:
        raise EnrollEmployeeError("valid 12-digit IIN is required", code="blocked")
    if not full_name:
        raise EnrollEmployeeError("full_name is required", code="blocked")
    return full_name, iin_digits


def _insert_enrolled_event(
    conn: Connection,
    *,
    employee_id: int,
    org_unit_id: int,
    position_id: int,
    employment_rate: float,
    effective_date: date,
    created_by: int,
    metadata: dict[str, Any],
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.employee_events (
                employee_id,
                event_type,
                event_class,
                lifecycle_status,
                metadata,
                effective_date,
                to_org_unit_id,
                to_position_id,
                to_rate,
                comment,
                created_by
            )
            VALUES (
                :employee_id,
                :event_type,
                :event_class,
                'APPROVED',
                CAST(:metadata AS jsonb),
                :effective_date,
                :to_org_unit_id,
                :to_position_id,
                :to_rate,
                :comment,
                :created_by
            )
            """
        ),
        {
            "employee_id": employee_id,
            "event_type": EVENT_TYPE_ENROLLED_FROM_IMPORT,
            "event_class": get_event_class(EVENT_TYPE_ENROLLED_FROM_IMPORT),
            "metadata": json.dumps(metadata, ensure_ascii=False),
            "effective_date": effective_date,
            "to_org_unit_id": org_unit_id,
            "to_position_id": position_id,
            "to_rate": employment_rate,
            "comment": "Добавлен в операционный контур из HR-импорта",
            "created_by": created_by,
        },
    )


ENROLLMENT_SOURCE_HR_IMPORT_NORMALIZED_RECORD = "hr_import_normalized_record"


def _persist_row_enroll_metadata(
    conn: Connection,
    *,
    row_id: int,
    employee_id: int,
    enrolled_by: int,
    source_normalized_record_id: int,
) -> None:
    """Merge enrollment metadata into the row payload without clobbering binding fields."""
    import_row = _load_row_payload(conn, row_id)
    payload = dict(import_row["payload"])
    metadata = dict(payload.get("metadata") or {})
    metadata["employee_binding_status"] = BINDING_STATUS_BOUND
    metadata["enrolled_employee_id"] = employee_id
    metadata["enrolled_from_record_id"] = source_normalized_record_id
    metadata["enrolled_by"] = enrolled_by
    metadata["enrolled_at"] = datetime.now(timezone.utc).isoformat()
    metadata["enrollment_source"] = ENROLLMENT_SOURCE_HR_IMPORT_NORMALIZED_RECORD
    payload["metadata"] = metadata
    conn.execute(
        text(
            """
            UPDATE public.hr_import_rows
            SET normalized_payload = CAST(:normalized_payload AS JSONB)
            WHERE row_id = :row_id
            """
        ),
        {
            "row_id": row_id,
            "normalized_payload": json.dumps(payload, ensure_ascii=False),
        },
    )


def _link_batch_rows_by_iin(
    conn: Connection,
    *,
    batch_id: int,
    iin_digits: str,
    employee_id: int,
    bound_by: int,
    source_normalized_record_id: int,
    row_ids: Optional[list[int]] = None,
) -> tuple[list[int], list[int]]:
    target_row_ids = row_ids if row_ids is not None else _find_batch_rows_by_iin(
        conn, batch_id=batch_id, iin_digits=iin_digits
    )
    linked_record_ids: list[int] = []
    for row_id in target_row_ids:
        binding = EmployeeBindingResult(
            employee_id=employee_id,
            status=BINDING_STATUS_BOUND,
            method=BINDING_METHOD_IIN,
            reason=f"Привязка при enrollment из import record #{source_normalized_record_id}",
        )
        persist_row_employee_binding(conn, row_id, binding, force=True)
        stats = propagate_employee_id_to_normalized_records(conn, row_id, employee_id)
        _persist_row_enroll_metadata(
            conn,
            row_id=row_id,
            employee_id=employee_id,
            enrolled_by=bound_by,
            source_normalized_record_id=source_normalized_record_id,
        )
        rows = conn.execute(
            text(
                """
                SELECT normalized_record_id
                FROM public.hr_import_normalized_records
                WHERE row_id = :row_id
                  AND employee_id = :employee_id
                  AND promoted_document_id IS NULL
                """
            ),
            {"row_id": row_id, "employee_id": employee_id},
        ).fetchall()
        linked_record_ids.extend(int(r[0]) for r in rows if r and r[0])
        _ = stats

    unique_records = sorted(set(linked_record_ids))
    return target_row_ids, unique_records


def enroll_employee_from_normalized_record(
    conn: Connection,
    record_id: int,
    *,
    created_by: int,
    request: EnrollEmployeeRequest,
) -> EnrollEmployeeResult:
    record_row = _fetch_normalized_record_row(conn, record_id)
    if record_row is None:
        raise NormalizedRecordNotFoundError(record_id)

    row_id = int(record_row["row_id"])
    batch_id = int(record_row["batch_id"])
    import_row = _load_row_payload(conn, row_id)
    batch_meta = _load_batch_meta(conn, batch_id)

    full_name, iin_digits = _validate_record_eligible(
        conn,
        record_row=record_row,
        import_row=import_row,
    )
    if request.full_name and request.full_name.strip():
        full_name = " ".join(request.full_name.strip().split())

    conflict = _check_iin_conflicts(conn, iin_digits)
    if conflict is not None:
        return EnrollEmployeeResult(
            dry_run=request.dry_run,
            outcome=OUTCOME_CONFLICT,
            conflict=conflict,
            preview={"full_name": full_name, "iin": iin_digits},
            provenance={
                "origin_type": "hr_import_normalized_record",
                "source_batch_id": batch_id,
                "source_batch_file_name": str(batch_meta.get("file_name") or ""),
                "source_row_id": row_id,
                "source_normalized_record_id": record_id,
                "trigger_record_kind": str(record_row.get("record_kind") or ""),
            },
        )

    dept_hint = _resolve_department_hint(conn, batch_id, iin=iin_digits, full_name=full_name)
    pos_hint = _resolve_position_hint(import_row["payload"])
    linked_row_ids_plan = _find_batch_rows_by_iin(conn, batch_id=batch_id, iin_digits=iin_digits)
    linked_record_ids_plan = _find_batch_normalized_records_by_iin(
        conn, batch_id=batch_id, iin_digits=iin_digits
    )

    warnings: list[str] = []
    if dept_hint and not dept_hint.get("org_unit_id"):
        warnings.append(f"Отделение «{dept_hint.get('value')}» не сопоставлено с org_unit")
    if not pos_hint:
        warnings.append("Должность не найдена в строке импорта — выберите вручную")

    preview: dict[str, Any] = {
        "full_name": full_name,
        "iin": iin_digits,
        "org_unit_id": request.org_unit_id,
        "org_unit_name": _org_unit_name(conn, request.org_unit_id),
        "position_id": request.position_id,
        "position_name": _position_name(conn, request.position_id),
        "date_from": (request.date_from or date.today()).isoformat(),
        "employment_rate": float(request.employment_rate if request.employment_rate is not None else 1.0),
        "org_unit_hint": dept_hint,
        "position_hint": pos_hint,
        "record_kind": str(record_row.get("record_kind") or ""),
        "source_sheet": import_row.get("source_sheet"),
        "source_row_number": import_row.get("source_row_number"),
    }
    provenance = {
        "origin_type": "hr_import_normalized_record",
        "source_batch_id": batch_id,
        "source_batch_file_name": str(batch_meta.get("file_name") or ""),
        "source_row_id": row_id,
        "source_normalized_record_id": record_id,
        "trigger_record_kind": str(record_row.get("record_kind") or ""),
        "source_field": str(record_row.get("source_field") or ""),
    }

    if request.dry_run:
        return EnrollEmployeeResult(
            dry_run=True,
            outcome=OUTCOME_READY,
            linked_records_count=len(linked_record_ids_plan),
            linked_record_ids=linked_record_ids_plan,
            linked_row_ids=linked_row_ids_plan,
            warnings=warnings,
            preview=preview,
            provenance=provenance,
        )

    if request.org_unit_id is None or int(request.org_unit_id) < 1:
        raise EnrollEmployeeError("org_unit_id is required", code="blocked")
    if request.position_id is None or int(request.position_id) < 1:
        raise EnrollEmployeeError("position_id is required", code="blocked")

    org_unit_id = int(request.org_unit_id)
    position_id = int(request.position_id)
    hired_on = request.date_from if request.date_from is not None else date.today()
    rate = float(request.employment_rate if request.employment_rate is not None else 1.0)

    org_check = conn.execute(
        text("SELECT 1 FROM public.org_units WHERE unit_id = :unit_id"),
        {"unit_id": org_unit_id},
    ).first()
    if org_check is None:
        raise EnrollEmployeeError(f"org_unit_id {org_unit_id} not found", code="blocked")
    pos_check = conn.execute(
        text("SELECT 1 FROM public.positions WHERE position_id = :position_id"),
        {"position_id": position_id},
    ).first()
    if pos_check is None:
        raise EnrollEmployeeError(f"position_id {position_id} not found", code="blocked")

    employee_id = int(
        conn.execute(
            text(
                """
                INSERT INTO public.employees (
                    full_name,
                    org_unit_id,
                    position_id,
                    date_from,
                    employment_rate,
                    is_active
                )
                VALUES (
                    :full_name,
                    :org_unit_id,
                    :position_id,
                    :date_from,
                    :employment_rate,
                    TRUE
                )
                RETURNING employee_id
                """
            ),
            {
                "full_name": full_name,
                "org_unit_id": org_unit_id,
                "position_id": position_id,
                "date_from": hired_on,
                "employment_rate": rate,
            },
        ).scalar_one()
    )

    _insert_employee_identity(
        conn,
        employee_id=employee_id,
        iin=iin_digits,
        created_by=created_by,
    )

    event_metadata = {
        **provenance,
        "matched_by": "iin",
        "link_same_iin_in_batch": bool(request.link_same_iin_in_batch),
    }
    _insert_enrolled_event(
        conn,
        employee_id=employee_id,
        org_unit_id=org_unit_id,
        position_id=position_id,
        employment_rate=rate,
        effective_date=hired_on,
        created_by=created_by,
        metadata=event_metadata,
    )

    write_security_event(
        event_type=EVENT_TYPE_ENROLLED_FROM_IMPORT,
        actor_user_id=created_by,
        target_employee_id=employee_id,
        metadata=event_metadata,
        conn=conn,
    )

    row_ids_to_link = linked_row_ids_plan if request.link_same_iin_in_batch else [row_id]
    linked_row_ids, linked_record_ids = _link_batch_rows_by_iin(
        conn,
        batch_id=batch_id,
        iin_digits=iin_digits,
        employee_id=employee_id,
        bound_by=created_by,
        source_normalized_record_id=record_id,
        row_ids=row_ids_to_link,
    )

    contact_result = ensure_operational_contact_for_employee(
        conn,
        employee_id=employee_id,
        full_name=full_name,
    )

    preview["org_unit_id"] = org_unit_id
    preview["org_unit_name"] = _org_unit_name(conn, org_unit_id)
    preview["position_id"] = position_id
    preview["position_name"] = _position_name(conn, position_id)

    return EnrollEmployeeResult(
        dry_run=False,
        outcome=OUTCOME_CREATED,
        created=True,
        employee_id=employee_id,
        contact_id=contact_result.contact_id,
        contact_created=contact_result.created,
        linked_records_count=len(linked_record_ids),
        linked_record_ids=linked_record_ids,
        linked_row_ids=linked_row_ids,
        warnings=warnings,
        preview=preview,
        provenance={
            **provenance,
            "created_by_user_id": created_by,
        },
    )
