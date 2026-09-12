"""ADR-065 first slice: atomic Person create/adopt and Employee link."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection
from app.services.iin_writer_protocol import lock_and_recheck_iin_tx
from app.services.hr_import_general_first_pass_service import parse_full_name, run_general_first_pass


class PersonLinkError(RuntimeError):
    def __init__(self, message: str, code: str, status: int = 409) -> None:
        self.code, self.status = code, status
        super().__init__(message)


def _name(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _norm_iin(value: Any) -> str:
    raw = str(value or "").strip()
    if len(raw) != 12 or not raw.isascii() or not raw.isdigit():
        raise PersonLinkError("IIN must be exactly 12 ASCII digits.", "IIN_INVALID", 422)
    return raw


def _parts(full_name: str) -> tuple[str | None, str | None, str | None]:
    p = full_name.split()
    return (p[0] if p else None, p[1] if len(p) > 1 else None, " ".join(p[2:]) if len(p) > 2 else None)


def canonical_payload_sha256(payload: Any) -> str:
    """Hash normalized payload without retaining it in an operation journal."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            pass
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_precondition(employee_id: int, full_name: str, records: list[dict[str, Any]]) -> str:
    # Keep the pure helper usable by older contract callers; apply/preflight
    # always pass fully loaded rows from PostgreSQL.
    if records and not isinstance(records[0], Mapping):
        records = [
            {"normalized_record_id": int(record), "row_id": 0, "batch_id": 0,
             "employee_id": None, "review_status": "", "normalized_payload": {}}
            for record in records
        ]
    canonical_records = sorted(
        ({
            "normalized_record_id": int(row["normalized_record_id"]),
            "row_id": int(row["row_id"]),
            "batch_id": int(row["batch_id"]),
            "employee_id": int(row["employee_id"]) if row["employee_id"] is not None else None,
            "review_status": str(row["review_status"]),
            "normalized_payload_sha256": canonical_payload_sha256(row["normalized_payload"]),
        } for row in records),
        key=lambda row: row["normalized_record_id"],
    )
    canonical = json.dumps({"employee_id": int(employee_id), "employee_full_name": _name(full_name), "records": canonical_records}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_request_fingerprint(*, employee_id: int, normalized_record_ids: list[int], expected_precondition: str, confirm_name_correction: bool, actor_user_id: int) -> str:
    canonical = json.dumps({"actor_user_id": int(actor_user_id), "confirm_name_correction": bool(confirm_name_correction), "employee_id": int(employee_id), "expected_precondition": expected_precondition, "normalized_record_ids": sorted(int(x) for x in normalized_record_ids)}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def link_person_tx(
    conn: Connection,
    *,
    employee_id: int,
    normalized_record_ids: list[int],
    expected_precondition: str,
    request_id: str,
    actor_user_id: int,
    confirm_name_correction: bool,
    scope_unit_ids: set[int] | None = None,
) -> dict[str, Any]:
    # Idempotency row is checked before any domain mutation.
    request_fingerprint = build_request_fingerprint(employee_id=employee_id, normalized_record_ids=normalized_record_ids, expected_precondition=expected_precondition, confirm_name_correction=confirm_name_correction, actor_user_id=actor_user_id)
    replay = conn.execute(
        text("SELECT request_id, employee_id, actor_user_id, request_fingerprint, person_id, decision, old_full_name, new_full_name "
             "FROM public.personnel_identity_link_operations WHERE request_id=:request_id FOR UPDATE"),
        {"request_id": request_id},
    ).mappings().first()
    if replay:
        if replay["request_fingerprint"] != request_fingerprint or int(replay["actor_user_id"]) != actor_user_id:
            raise PersonLinkError("request_id is already used with a different operation payload.", "REQUEST_ID_REUSE_CONFLICT")
        return {
            "request_id": request_id, "employee_id": employee_id, "person_id": int(replay["person_id"]),
            "decision": "REPLAY", "employee_full_name": replay["new_full_name"] or replay["old_full_name"],
            "canonical_full_name": replay["new_full_name"] or replay["old_full_name"], "name_corrected": replay["old_full_name"] != replay["new_full_name"],
        }

    # ADR-065 lock order: employee identity/employee first, then Person identity.
    employee = conn.execute(
        text("SELECT employee_id, person_id, full_name, org_unit_id, operational_status "
             "FROM public.employees WHERE employee_id=:employee_id FOR UPDATE"),
        {"employee_id": employee_id},
    ).mappings().first()
    if not employee:
        raise PersonLinkError("Employee does not exist.", "EMPLOYEE_NOT_FOUND", 404)
    if scope_unit_ids is not None and employee["org_unit_id"] not in scope_unit_ids:
        raise PersonLinkError("Employee is outside the operator organization scope.", "ORG_SCOPE_DENIED", 403)
    old_name = _name(employee["full_name"])
    if employee["person_id"] is not None:
        raise PersonLinkError("Employee already has a Person link.", "EMPLOYEE_ALREADY_LINKED")
    if employee["operational_status"] not in ("active", "suspended", "draft"):
        raise PersonLinkError("Employee is not eligible for Person linking.", "EMPLOYEE_STATE_NOT_ELIGIBLE")

    identities = list(conn.execute(text("SELECT identity_value FROM public.employee_identities "
        "WHERE employee_id=:employee_id AND identity_type='IIN' AND valid_to IS NULL FOR UPDATE"), {"employee_id": employee_id}).scalars())
    if len(identities) != 1:
        raise PersonLinkError("Employee must have exactly one active IIN.", "EMPLOYEE_IIN_CONFLICT")
    iin = _norm_iin(identities[0])
    # The identity read above establishes the single target IIN; all subsequent conflict checks
    # and the possible Person create are serialized by the shared transaction lock.
    lock_and_recheck_iin_tx(conn, iin=iin)
    other_employees = list(conn.execute(text(
        "SELECT employee_id FROM public.employee_identities "
        "WHERE identity_type='IIN' AND identity_value=:iin AND valid_to IS NULL "
        "AND employee_id<>:employee_id ORDER BY employee_id FOR UPDATE"
    ), {"iin": iin, "employee_id": employee_id}).scalars())
    if other_employees:
        raise PersonLinkError("IIN is linked to another active Employee.", "EMPLOYEE_IIN_CONFLICT")

    records = list(conn.execute(text(
        "SELECT nr.normalized_record_id, nr.row_id, nr.batch_id, nr.employee_id, nr.review_status, "
        "       ir.normalized_payload "
        "FROM public.hr_import_normalized_records nr "
        "JOIN public.hr_import_rows ir "
        "  ON ir.row_id = nr.row_id AND ir.batch_id = nr.batch_id "
        "WHERE nr.normalized_record_id IN :ids "
        "ORDER BY nr.normalized_record_id FOR UPDATE OF nr, ir"
    ).bindparams(bindparam("ids", expanding=True)), {"ids": sorted(normalized_record_ids)}).mappings())
    if len(records) != len(set(normalized_record_ids)):
        raise PersonLinkError("Selected normalized records are incomplete.", "IMPORT_RECORD_NOT_FOUND", 422)
    if any(str(row["review_status"] or "").lower() != "approved" for row in records):
        raise PersonLinkError("Selected normalized records must be approved before Person linking.", "IMPORT_RECORD_NOT_APPROVED")
    names = []
    for row in records:
        if row["employee_id"] not in (None, employee_id):
            raise PersonLinkError("Selected records belong to another Employee.", "IMPORT_RECORD_OWNERSHIP_CONFLICT")
        payload = row["normalized_payload"]
        if isinstance(payload, str): payload = json.loads(payload)
        if not isinstance(payload, dict) or _norm_iin(payload.get("iin")) != iin:
            raise PersonLinkError("Selected records do not resolve to one IIN.", "IMPORT_IIN_CONFLICT")
        names.append(_name(payload.get("full_name")))
    if not names or len(set(names)) != 1 or not names[0]:
        raise PersonLinkError("Selected records must contain one non-empty full name.", "IMPORT_NAME_CONFLICT", 422)
    source_name = names[0]
    if expected_precondition != build_precondition(employee_id, old_name, records):
        raise PersonLinkError("Precondition is stale; rerun preflight.", "STALE_PRECONDITION")
    if source_name != old_name and not confirm_name_correction:
        raise PersonLinkError("Name correction requires explicit confirmation.", "NAME_CORRECTION_CONFIRMATION_REQUIRED")

    candidates = list(conn.execute(text("SELECT person_id, full_name, person_status, merged_into_person_id "
        "FROM public.persons WHERE iin=:iin ORDER BY person_id FOR UPDATE"), {"iin": iin}).mappings())
    if len(candidates) > 1:
        raise PersonLinkError("Multiple Persons match this IIN.", "PERSON_IIN_AMBIGUOUS")
    person_id: int
    decision: str
    canonical_name = source_name if confirm_name_correction else old_name
    if candidates:
        p = candidates[0]
        if p["person_status"] != "active" or p["merged_into_person_id"] is not None:
            raise PersonLinkError("Matching Person is not compatible.", "PERSON_INCOMPATIBLE")
        conflict = conn.execute(text("SELECT employee_id FROM public.employees WHERE person_id=:person_id AND employee_id<>:employee_id "
            "AND operational_status IN ('active','suspended','draft') FOR UPDATE"), {"person_id": int(p["person_id"]), "employee_id": employee_id}).scalar_one_or_none()
        if conflict is not None:
            raise PersonLinkError("Person is already linked to another active Employee.", "PERSON_EMPLOYEE_CONFLICT")
        person_id, decision = int(p["person_id"]), "ADOPT"
        if confirm_name_correction and _name(p["full_name"]) != source_name:
            conn.execute(text("UPDATE public.persons SET full_name=:full_name, updated_at=now() WHERE person_id=:person_id"), {"full_name": source_name, "person_id": person_id})
    else:
        parsed_name, _ = parse_full_name(canonical_name)
        person_id = int(conn.execute(text("INSERT INTO public.persons (iin, full_name, last_name, first_name, middle_name, match_key, person_status, source) "
            "VALUES (:iin,:full_name,:last_name,:first_name,:middle_name,:match_key,'active','enrollment') RETURNING person_id"), {
                "iin": iin, "full_name": canonical_name,
                "last_name": parsed_name.last_name if parsed_name else None,
                "first_name": parsed_name.first_name if parsed_name else None,
                "middle_name": parsed_name.middle_name if parsed_name else None,
                "match_key": f"adr065:employee:{employee_id}:iin:{iin}",
            }).scalar_one())
        decision = "CREATE"
    conn.execute(text("UPDATE public.employees SET person_id=:person_id, full_name=:full_name WHERE employee_id=:employee_id AND person_id IS NULL"), {"person_id": person_id, "full_name": canonical_name, "employee_id": employee_id})
    if conn.execute(text("SELECT person_id FROM public.employees WHERE employee_id=:employee_id"), {"employee_id": employee_id}).scalar_one() != person_id:
        raise PersonLinkError("Employee link changed concurrently.", "CONCURRENT_MODIFICATION")
    # The general-information first pass is part of the same transaction as
    # creating/adopting the Person link.  It has its own PII-free idempotency
    # key, so retrying this operation cannot generate duplicate audit events.
    run_general_first_pass(conn, employee_ids=[employee_id])
    conn.execute(text("INSERT INTO public.personnel_identity_link_operations (request_id, request_fingerprint, actor_user_id, employee_id, person_id, decision, old_full_name, new_full_name, normalized_record_ids) "
        "VALUES (:request_id,:fingerprint,:actor,:employee,:person,:decision,:old_name,:new_name,:record_ids)"), {
            "request_id": request_id, "actor": actor_user_id, "employee": employee_id, "person": person_id,
            "fingerprint": request_fingerprint,
            "decision": decision, "old_name": old_name, "new_name": canonical_name, "record_ids": json.dumps(sorted(normalized_record_ids)),
        })
    return {"request_id": request_id, "employee_id": employee_id, "person_id": person_id, "decision": decision,
            "employee_full_name": canonical_name, "canonical_full_name": canonical_name, "name_corrected": old_name != canonical_name}
