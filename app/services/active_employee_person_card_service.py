"""HR-confirmed creation of a Person card for an already active Employee.

This is deliberately separate from ADR-065 control-list repair: an operational
Employee can already have a current job while it has no Person/PPR identity.
The operation creates only that identity link; it never creates or changes a
``person_assignments`` row.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.adr048_person_resolution_service import (
    Adr048PersonResolution,
    resolve_person_create_or_link_exact_iin_tx,
)
from app.services.adr065_person_link_service import PersonLinkError, _parts
from app.services.iin_writer_protocol import lock_and_recheck_iin_tx


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _safe_iin(iin: str) -> dict[str, Any]:
    return {"present": True, "last4": iin[-4:]}


def _load_employee(conn: Connection, employee_id: int, *, lock: bool = False) -> dict[str, Any] | None:
    suffix = " FOR UPDATE" if lock else ""
    row = conn.execute(
        text(
            "SELECT employee_id, person_id, full_name, org_unit_id, is_active, operational_status "
            "FROM public.employees WHERE employee_id=:employee_id" + suffix
        ),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    return dict(row) if row else None


def _load_active_iin(conn: Connection, employee_id: int, *, lock: bool = False) -> str | None:
    suffix = " FOR UPDATE" if lock else ""
    rows = conn.execute(
        text(
            "SELECT identity_value FROM public.employee_identities "
            "WHERE employee_id=:employee_id AND identity_type='IIN' AND valid_to IS NULL "
            "ORDER BY identity_id" + suffix
        ),
        {"employee_id": int(employee_id)},
    ).scalars().all()
    if len(rows) != 1:
        return None
    return str(rows[0])


def build_active_employee_card_precondition(employee: dict[str, Any], iin: str) -> str:
    """Opaque optimistic-concurrency token; it never exposes the IIN."""
    return _fingerprint(
        {
            "workflow": "ACTIVE_EMPLOYEE_PERSON_CARD_V1",
            "employee_id": int(employee["employee_id"]),
            "person_id": employee.get("person_id"),
            "full_name": " ".join(str(employee.get("full_name") or "").split()),
            "is_active": bool(employee.get("is_active")),
            "operational_status": str(employee.get("operational_status") or ""),
            "iin": iin,
        }
    )


def _resolution_blocker(resolution: Adr048PersonResolution) -> dict[str, str] | None:
    if resolution.decision == "AMBIGUOUS":
        return {"code": "PERSON_IDENTITY_AMBIGUOUS", "detail": "More than one Person has the exact employee identity."}
    if resolution.decision == "P1_ADOPT":
        return {"code": "PERSON_ALREADY_EXISTS", "detail": "An exact Person already exists; this create-only workflow cannot adopt it."}
    if resolution.decision == "INCOMPATIBLE":
        return {"code": "PERSON_INCOMPATIBLE", "detail": "The exact Person candidate is not active and compatible."}
    if resolution.decision == "CONFLICT":
        return {"code": "PERSON_EMPLOYEE_CONFLICT", "detail": "The exact Person identity conflicts with an Employee link."}
    return None


def active_employee_person_card_preflight(
    conn: Connection, *, employee_id: int, scope_unit_ids: set[int] | None = None
) -> dict[str, Any]:
    """Read-only eligibility check for the HR confirmation dialog."""
    blockers: list[dict[str, str]] = []

    def block(code: str, detail: str) -> None:
        if code not in {item["code"] for item in blockers}:
            blockers.append({"code": code, "detail": detail})

    employee = _load_employee(conn, employee_id)
    if employee is None:
        block("EMPLOYEE_NOT_FOUND", "Employee does not exist.")
        return {"employee_id": int(employee_id), "ready": False, "blockers": blockers, "expected_precondition": None}
    if scope_unit_ids is not None and employee.get("org_unit_id") not in scope_unit_ids:
        block("ORG_SCOPE_DENIED", "Employee is outside the operator organization scope.")
    if employee.get("person_id") is not None:
        block("EMPLOYEE_ALREADY_LINKED", "Employee already has a Person link.")
    if employee.get("operational_status") != "active" or employee.get("is_active") is not True:
        block("EMPLOYEE_STATE_NOT_ELIGIBLE", "Employee must be active.")
    iin = _load_active_iin(conn, employee_id)
    if iin is None:
        block("EMPLOYEE_IIN_CONFLICT", "Employee must have exactly one active IIN identity.")
        resolution = None
    else:
        resolution = resolve_person_create_or_link_exact_iin_tx(
            conn, iin=iin, target_employee_id=int(employee_id)
        )
        if item := _resolution_blocker(resolution):
            block(item["code"], item["detail"])

    return {
        "employee_id": int(employee_id),
        "employee_full_name": str(employee.get("full_name") or "") or None,
        "operational_status": employee.get("operational_status"),
        "iin": _safe_iin(iin) if iin else {"present": False, "last4": None},
        "person_candidates": [
            {"person_id": candidate.person_id, "person_status": candidate.person_status, "compatible": candidate.compatible}
            for candidate in (resolution.candidates if resolution else ())
        ],
        "ready": not blockers,
        "blockers": blockers,
        "expected_precondition": build_active_employee_card_precondition(employee, iin) if iin and not blockers else None,
    }


def create_active_employee_person_card_tx(
    conn: Connection,
    *,
    employee_id: int,
    expected_precondition: str,
    request_id: str,
    actor_user_id: int,
    hr_confirmed: bool,
    scope_unit_ids: set[int] | None = None,
) -> dict[str, Any]:
    """Create Person and set ``employees.person_id`` in one caller-owned transaction."""
    if hr_confirmed is not True:
        raise PersonLinkError("HR confirmation is required.", "HR_CONFIRMATION_REQUIRED", 422)
    request_fingerprint = _fingerprint(
        {"workflow": "ACTIVE_EMPLOYEE_PERSON_CARD_V1", "employee_id": int(employee_id),
         "expected_precondition": expected_precondition, "hr_confirmed": True, "actor_user_id": int(actor_user_id)}
    )
    replay = conn.execute(
        text("SELECT request_fingerprint, employee_id, actor_user_id, person_id, decision, old_full_name, new_full_name "
             "FROM public.personnel_identity_link_operations WHERE request_id=:request_id FOR UPDATE"),
        {"request_id": request_id},
    ).mappings().first()
    if replay:
        if (str(replay["request_fingerprint"]) != request_fingerprint
                or int(replay["employee_id"]) != int(employee_id)
                or int(replay["actor_user_id"]) != int(actor_user_id)):
            raise PersonLinkError("request_id is already used with a different operation payload.", "REQUEST_ID_REUSE_CONFLICT")
        return {"request_id": request_id, "employee_id": int(employee_id), "person_id": int(replay["person_id"]),
                "decision": "REPLAY", "employee_full_name": replay["new_full_name"] or replay["old_full_name"]}

    employee = _load_employee(conn, employee_id, lock=True)
    if employee is None:
        raise PersonLinkError("Employee does not exist.", "EMPLOYEE_NOT_FOUND", 404)
    if scope_unit_ids is not None and employee.get("org_unit_id") not in scope_unit_ids:
        raise PersonLinkError("Employee is outside the operator organization scope.", "ORG_SCOPE_DENIED", 403)
    if employee.get("person_id") is not None:
        raise PersonLinkError("Employee already has a Person link.", "EMPLOYEE_ALREADY_LINKED")
    if employee.get("operational_status") != "active" or employee.get("is_active") is not True:
        raise PersonLinkError("Employee must be active.", "EMPLOYEE_STATE_NOT_ELIGIBLE")
    iin = _load_active_iin(conn, employee_id, lock=True)
    if iin is None:
        raise PersonLinkError("Employee must have exactly one active IIN identity.", "EMPLOYEE_IIN_CONFLICT")
    if expected_precondition != build_active_employee_card_precondition(employee, iin):
        raise PersonLinkError("Precondition is stale; rerun preflight.", "STALE_PRECONDITION")

    locked = lock_and_recheck_iin_tx(conn, iin=iin)
    if set(locked.active_identity_employee_ids) != {int(employee_id)}:
        raise PersonLinkError("IIN is linked to another active Employee.", "EMPLOYEE_IIN_CONFLICT")
    if len(locked.person_ids) > 1:
        raise PersonLinkError("Multiple Persons match this IIN.", "PERSON_IDENTITY_AMBIGUOUS")
    if locked.person_ids:
        raise PersonLinkError("An exact Person already exists.", "PERSON_ALREADY_EXISTS")

    full_name = " ".join(str(employee.get("full_name") or "").split())
    if not full_name:
        raise PersonLinkError("Employee full name is required.", "EMPLOYEE_NAME_REQUIRED", 422)
    last_name, first_name, middle_name = _parts(full_name)
    person_id = int(conn.execute(
        text("INSERT INTO public.persons (iin,full_name,last_name,first_name,middle_name,match_key,person_status,source) "
             "VALUES (:iin,:full_name,:last_name,:first_name,:middle_name,:match_key,'active','enrollment') "
             "RETURNING person_id"),
        {"iin": iin, "full_name": full_name, "last_name": last_name, "first_name": first_name,
         "middle_name": middle_name, "match_key": f"active-employee-card:{int(employee_id)}:iin:{iin}"},
    ).scalar_one())
    conn.execute(
        text("UPDATE public.employees SET person_id=:person_id WHERE employee_id=:employee_id AND person_id IS NULL"),
        {"person_id": person_id, "employee_id": int(employee_id)},
    )
    if conn.execute(text("SELECT person_id FROM public.employees WHERE employee_id=:employee_id"), {"employee_id": int(employee_id)}).scalar_one() != person_id:
        raise PersonLinkError("Employee link changed concurrently.", "CONCURRENT_MODIFICATION")
    # Immutable ADR-065 operation journal is the audit ledger.  An empty record
    # set distinguishes this active-employee workflow from control-list repair.
    conn.execute(
        text("INSERT INTO public.personnel_identity_link_operations "
             "(request_id,request_fingerprint,actor_user_id,employee_id,person_id,decision,old_full_name,new_full_name,normalized_record_ids) "
             "VALUES (:request_id,:request_fingerprint,:actor_user_id,:employee_id,:person_id,'CREATE',:full_name,:full_name,'[]'::jsonb)"),
        {"request_id": request_id, "request_fingerprint": request_fingerprint, "actor_user_id": int(actor_user_id),
         "employee_id": int(employee_id), "person_id": person_id, "full_name": full_name},
    )
    return {"request_id": request_id, "employee_id": int(employee_id), "person_id": person_id,
            "decision": "CREATE", "employee_full_name": full_name}
