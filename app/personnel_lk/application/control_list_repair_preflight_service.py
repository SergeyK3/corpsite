"""Read-only exact-IIN discovery for ADR-065 existing-card repair."""
from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from app.services.adr048_person_resolution_service import (
    Adr048PersonResolution,
    resolve_person_create_or_link_exact_iin_tx,
)
from app.personnel_lk.application.personnel_order_evidence_fingerprint import (
    EvidenceFingerprintError,
    EvidenceKeySnapshot,
    verify_personnel_order_evidence_tx,
)

COMPOSITE_MODE = "LINK_AND_OPEN_MISSING_ASSIGNMENT"
COMPOSITE_OUTCOME = "EMPLOYEE_PERSON_AND_ASSIGNMENT_REPAIRED"

ASSIGNMENT_INPUTS = (
    "org_unit",
    "position",
    "rate",
    "employment_type",
    "is_primary",
    "start_date",
    "evidence",
    "reason_code",
)


def _safe_iin(iin: str | None) -> dict[str, Any]:
    return {"present": iin is not None, "last4": iin[-4:] if iin else None}


def _normalize_confirmed_name(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    normalized = " ".join(normalized.split())
    return unicodedata.normalize("NFC", normalized.casefold())


def _complete_mapping(value: Any, fields: tuple[str, ...]) -> bool:
    if not isinstance(value, Mapping):
        return False
    for field in fields:
        item = value.get(field)
        if item is None or (isinstance(item, str) and not item.strip()):
            return False
    return True


def _assignment_input_state(
    intent: Mapping[str, Any] | None,
) -> tuple[list[str], list[str]]:
    if intent is None:
        return sorted((*ASSIGNMENT_INPUTS, "verifier_confirmation")), []

    missing: list[str] = []
    invalid: list[str] = []
    if not _complete_mapping(
        intent.get("org_unit"),
        (
            "org_unit_id",
            "org_unit_normalized_stable_code",
            "operator_confirmed_normalized_org_name",
        ),
    ):
        missing.append("org_unit")
    if not _complete_mapping(
        intent.get("position"),
        ("position_id", "operator_confirmed_normalized_position_name"),
    ):
        missing.append("position")
    for field in ("rate", "employment_type", "start_date", "reason_code"):
        value = intent.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    if intent.get("is_primary") is None:
        missing.append("is_primary")
    elif intent.get("is_primary") is not True:
        invalid.append("is_primary")

    evidence = intent.get("evidence")
    if not isinstance(evidence, Mapping):
        missing.append("evidence")
    else:
        evidence_type = evidence.get("evidence_type")
        if evidence_type == "PERSONNEL_ORDER":
            required = (
                "personnel_order_id",
                "evidence_record_id",
                "evidence_profile_id",
                "evidence_profile_version",
                "evidence_key_id",
                "evidence_fingerprint",
                "admissibility_confirmed",
            )
        elif evidence_type == "EXTERNAL_REFERENCE":
            required = ("evidence_fingerprint", "admissibility_confirmed")
        else:
            required = ()
            invalid.append("evidence")
        if required and not _complete_mapping(evidence, required):
            missing.append("evidence")
        elif evidence.get("admissibility_confirmed") is not True:
            invalid.append("evidence")

    verifier = intent.get("verifier_confirmation")
    if not _complete_mapping(
        verifier,
        ("verifier_user_id", "confirmation_at", "confirmation_reference"),
    ):
        missing.append("verifier_confirmation")
    return sorted(set(missing)), sorted(set(invalid))


def _load_import_records(conn: Connection, iin: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT b.batch_id,
                   r.row_id,
                   r.employee_id,
                   COALESCE(
                       jsonb_agg(
                           jsonb_build_object(
                               'normalized_record_id', nr.normalized_record_id,
                               'batch_id', nr.batch_id,
                               'row_id', nr.row_id,
                               'employee_id', nr.employee_id
                           ) ORDER BY nr.normalized_record_id
                       ) FILTER (WHERE nr.normalized_record_id IS NOT NULL),
                       '[]'::jsonb
                   ) AS normalized_records
              FROM public.hr_import_batches b
              JOIN public.hr_import_rows r ON r.batch_id = b.batch_id
              LEFT JOIN public.hr_import_normalized_records nr
                     ON nr.row_id = r.row_id
             WHERE b.source_type = 'HR_CONTROL_LIST'
               AND r.normalized_payload ->> 'iin' = :iin
             GROUP BY b.batch_id, r.row_id, r.employee_id
             ORDER BY b.batch_id, r.row_id
            """
        ),
        {"iin": iin},
    ).mappings()
    return [
        {
            "batch_id": int(row["batch_id"]),
            "row_id": int(row["row_id"]),
            "employee_id": int(row["employee_id"]) if row["employee_id"] is not None else None,
            "normalized_records": [
                {
                    "normalized_record_id": int(record["normalized_record_id"]),
                    "batch_id": int(record["batch_id"]),
                    "row_id": int(record["row_id"]),
                    "employee_id": (
                        int(record["employee_id"])
                        if record["employee_id"] is not None
                        else None
                    ),
                }
                for record in row["normalized_records"]
            ],
        }
        for row in rows
    ]


def _load_import_selection(
    conn: Connection,
    selection: Mapping[str, Any],
    *,
    iin: str,
    block: Any,
) -> dict[str, Any] | None:
    batch_id = int(selection["batch_id"])
    row_id = int(selection["row_id"])
    requested_ids = sorted(int(item) for item in selection["normalized_record_ids"])

    batch = conn.execute(
        text(
            "SELECT batch_id, source_type FROM public.hr_import_batches "
            "WHERE batch_id=:batch_id"
        ),
        {"batch_id": batch_id},
    ).mappings().first()
    if batch is None:
        block("IMPORT_BATCH_NOT_FOUND", "Selected import batch does not exist.")
        return None
    if batch["source_type"] != "HR_CONTROL_LIST":
        block("IMPORT_BATCH_SOURCE_MISMATCH", "Selected batch is not an HR control list.")

    row = conn.execute(
        text(
            """
            SELECT row_id, batch_id, employee_id, normalized_payload ->> 'iin' AS iin
              FROM public.hr_import_rows
             WHERE row_id=:row_id
            """
        ),
        {"row_id": row_id},
    ).mappings().first()
    if row is None:
        block("IMPORT_ROW_NOT_FOUND", "Selected import row does not exist.")
        return None
    if int(row["batch_id"]) != batch_id:
        block("IMPORT_ROW_BATCH_MISMATCH", "Selected row belongs to another batch.")
    if row["iin"] != iin:
        block("IMPORT_ROW_IIN_MISMATCH", "Selected row does not have the exact IIN.")

    statement = text(
        """
        SELECT normalized_record_id, batch_id, row_id, employee_id
          FROM public.hr_import_normalized_records
         WHERE normalized_record_id IN :record_ids
         ORDER BY normalized_record_id
        """
    ).bindparams(bindparam("record_ids", expanding=True))
    records = [
        dict(record)
        for record in conn.execute(statement, {"record_ids": requested_ids}).mappings()
    ]
    found_ids = {int(record["normalized_record_id"]) for record in records}
    if found_ids != set(requested_ids):
        block(
            "IMPORT_NORMALIZED_RECORD_NOT_FOUND",
            "At least one selected normalized record does not exist.",
        )
    if any(
        int(record["batch_id"]) != batch_id or int(record["row_id"]) != row_id
        for record in records
    ):
        block(
            "IMPORT_NORMALIZED_RECORD_SCOPE_MISMATCH",
            "A selected normalized record belongs to another batch or row.",
        )

    all_row_records = [
        dict(record)
        for record in conn.execute(
            text(
                "SELECT normalized_record_id, batch_id, row_id, employee_id "
                "FROM public.hr_import_normalized_records "
                "WHERE row_id=:row_id ORDER BY normalized_record_id"
            ),
            {"row_id": row_id},
        ).mappings()
    ]
    if any(int(record["batch_id"]) != batch_id for record in all_row_records):
        block(
            "IMPORT_NORMALIZED_RECORD_BATCH_MISMATCH",
            "A normalized-record sibling for the selected row belongs to another batch.",
        )
    all_row_ids = {
        int(record["normalized_record_id"]) for record in all_row_records
    }
    if set(requested_ids) != all_row_ids:
        block(
            "IMPORT_SELECTION_INCOMPLETE",
            "Exact selection must contain the complete normalized-record set for the row.",
        )
    return {
        "batch_id": batch_id,
        "row_id": row_id,
        "employee_id": int(row["employee_id"]) if row["employee_id"] is not None else None,
        "normalized_records": all_row_records,
        "normalized_record_ids": requested_ids,
    }


def _load_employees(conn: Connection, iin: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            text(
                """
                SELECT e.employee_id, e.person_id, e.operational_status, ei.identity_value
                  FROM public.employee_identities ei
                  JOIN public.employees e ON e.employee_id = ei.employee_id
                 WHERE ei.identity_type = 'IIN'
                   AND ei.identity_value = :iin
                   AND ei.valid_to IS NULL
                 ORDER BY e.employee_id
                """
            ),
            {"iin": iin},
        ).mappings()
    ]


def _employee_has_other_active_iin(conn: Connection, employee_id: int, iin: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM public.employee_identities
                     WHERE employee_id=:employee_id AND identity_type='IIN'
                       AND valid_to IS NULL AND identity_value<>:iin
                )
                """
            ),
            {"employee_id": employee_id, "iin": iin},
        ).scalar_one()
    )


def _load_primary_assignments(
    conn: Connection, person_ids: list[int]
) -> list[dict[str, Any]]:
    if not person_ids:
        return []
    statement = text(
        """
        SELECT assignment_id, person_id, lifecycle_status, active_flag, is_primary
          FROM public.person_assignments
         WHERE person_id IN :person_ids
           AND is_primary=TRUE AND lifecycle_status<>'voided'
         ORDER BY person_id, assignment_id
        """
    ).bindparams(bindparam("person_ids", expanding=True))
    return [
        dict(row)
        for row in conn.execute(statement, {"person_ids": person_ids}).mappings()
    ]


def _load_business_date(conn: Connection, *, block: Any) -> date | None:
    business_date = conn.execute(
        text(
            "SELECT ((transaction_timestamp() AT TIME ZONE 'UTC') "
            "+ INTERVAL '5 hours')::date"
        )
    ).scalar_one()
    relation = conn.execute(
        text("SELECT to_regclass('public.person_assignment_activation_watermark')")
    ).scalar_one()
    if relation is None:
        block(
            "ACTIVE_STATE_SCHEMA_UNAVAILABLE",
            "Assignment activation watermark schema is unavailable.",
        )
        return None
    columns = {
        row["column_name"]: (row["data_type"], row["is_nullable"])
        for row in conn.execute(
            text(
                "SELECT column_name,data_type,is_nullable FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='person_assignment_activation_watermark'"
            )
        ).mappings()
    }
    required = {
        "singleton": ("boolean", "NO"),
        "effective_date": ("date", "NO"),
        "processed_at": ("timestamp with time zone", "NO"),
        "generation": ("bigint", "NO"),
        "updated_at": ("timestamp with time zone", "NO"),
    }
    if any(columns.get(name) != shape for name, shape in required.items()):
        block("ACTIVE_STATE_SCHEMA_UNAVAILABLE", "Assignment activation watermark schema is incompatible.")
        return None
    rows = list(
        conn.execute(
            text(
                "SELECT singleton,effective_date,processed_at,generation,updated_at "
                "FROM public.person_assignment_activation_watermark ORDER BY singleton"
            )
        ).mappings()
    )
    if (
        len(rows) != 1
        or rows[0]["singleton"] is not True
        or rows[0]["effective_date"] is None
        or rows[0]["processed_at"] is None
        or rows[0]["updated_at"] is None
        or rows[0]["processed_at"] > rows[0]["updated_at"]
        or rows[0]["generation"] is None
        or int(rows[0]["generation"]) < 1
    ):
        block("ACTIVE_STATE_WATERMARK_INVALID", "Assignment activation watermark is invalid.")
        return None
    watermark_date = rows[0]["effective_date"]
    if watermark_date < business_date:
        block("ACTIVE_STATE_STALE", "Assignment activation watermark is stale.")
        return None
    if watermark_date > business_date:
        block("ACTIVE_STATE_FUTURE", "Assignment activation watermark is in the future.")
        return None
    return business_date


def _validate_reference_inputs(
    conn: Connection,
    intent: Mapping[str, Any] | None,
    *,
    business_date: date | None,
    evidence_key_snapshot: EvidenceKeySnapshot | None,
    block: Any,
) -> list[str]:
    invalid: list[str] = []
    if intent is None:
        return invalid
    org = intent.get("org_unit")
    if isinstance(org, Mapping) and org.get("org_unit_id") is not None:
        row = conn.execute(
            text(
                "SELECT unit_id, name, code, is_active FROM public.org_units "
                "WHERE unit_id=:unit_id"
            ),
            {"unit_id": int(org["org_unit_id"])},
        ).mappings().first()
        if row is None:
            block("ORG_UNIT_NOT_FOUND", "Confirmed org unit does not exist.")
            invalid.append("org_unit")
        elif row["is_active"] is not True:
            block("ORG_UNIT_INACTIVE", "Confirmed org unit is inactive.")
            invalid.append("org_unit")
        elif (
            org.get("org_unit_normalized_stable_code")
            != str(row["code"] or "")
            or org.get("operator_confirmed_normalized_org_name")
            != _normalize_confirmed_name(str(row["name"] or ""))
        ):
            block(
                "ORG_UNIT_CONFIRMATION_MISMATCH",
                "Confirmed org unit tuple does not match the selected row.",
            )
            invalid.append("org_unit")

    position = intent.get("position")
    if isinstance(position, Mapping) and position.get("position_id") is not None:
        row = conn.execute(
            text("SELECT position_id, name FROM public.positions WHERE position_id=:id"),
            {"id": int(position["position_id"])},
        ).mappings().first()
        if row is None:
            block("POSITION_NOT_FOUND", "Confirmed position does not exist.")
            invalid.append("position")
        elif position.get(
            "operator_confirmed_normalized_position_name"
        ) != _normalize_confirmed_name(str(row["name"] or "")):
            block("POSITION_NAME_MISMATCH", "Confirmed position name does not match.")
            invalid.append("position")

    verifier = intent.get("verifier_confirmation")
    if isinstance(verifier, Mapping) and verifier.get("verifier_user_id") is not None:
        exists = conn.execute(
            text("SELECT EXISTS (SELECT 1 FROM public.users WHERE user_id=:id)"),
            {"id": int(verifier["verifier_user_id"])},
        ).scalar_one()
        if not exists:
            block("VERIFIER_NOT_FOUND", "Confirmed verifier does not exist.")
            invalid.append("verifier_confirmation")

    evidence = intent.get("evidence")
    if isinstance(evidence, Mapping) and evidence.get("evidence_type") == "PERSONNEL_ORDER":
        order_id = evidence.get("personnel_order_id")
        record_id = evidence.get("evidence_record_id")
        if order_id is not None and record_id is not None:
            try:
                verify_personnel_order_evidence_tx(
                    conn,
                    order_id=int(order_id),
                    item_id=int(record_id),
                    requested_hex=str(evidence.get("evidence_fingerprint")),
                    profile_id=str(evidence.get("evidence_profile_id")),
                    profile_version=int(evidence.get("evidence_profile_version")),
                    key_id=str(evidence.get("evidence_key_id")),
                    key_snapshot=evidence_key_snapshot,
                )
            except EvidenceFingerprintError as exc:
                block(exc.code, "Personnel-order evidence verification failed.")
                invalid.append("evidence")
    start_date = intent.get("start_date")
    if isinstance(start_date, date) and business_date is not None and start_date > business_date:
        block(
            "INVALID_ASSIGNMENT_DATES",
            "Assignment start date is later than business date D.",
        )
        invalid.append("start_date")
    return list(dict.fromkeys(invalid))


def _resolution_blockers(
    resolution: Adr048PersonResolution,
    *,
    block: Any,
) -> None:
    if resolution.decision == "AMBIGUOUS":
        block("AMBIGUOUS_PERSON", "ADR-048 exact identity resolution is ambiguous.")
    elif resolution.decision == "INCOMPATIBLE":
        block("INCOMPATIBLE_PERSON", "ADR-048 rejected the exact-IIN Person candidate.")
    elif resolution.decision == "CONFLICT":
        if "TARGET_EMPLOYEE_ALREADY_LINKED" in resolution.reason_codes:
            block("EMPLOYEE_ALREADY_LINKED", "Employee already has the resolved Person link.")
        elif "TARGET_EMPLOYEE_PERSON_IDENTITY_CONFLICT" in resolution.reason_codes:
            block(
                "EMPLOYEE_PERSON_IIN_CONFLICT",
                "Employee link conflicts with ADR-048 exact identity resolution.",
            )
        else:
            block(
                "PERSON_ALREADY_LINKED",
                "ADR-048 found an active Employee ownership conflict.",
            )


def control_list_repair_preflight(
    conn: Connection,
    *,
    iin: str,
    import_selection: Mapping[str, Any] | None,
    assignment_intent: Mapping[str, Any] | None,
    evidence_key_snapshot: EvidenceKeySnapshot | None = None,
) -> dict[str, Any]:
    """Read and classify one exact-IIN snapshot; the caller owns the read-only tx."""
    import_records = _load_import_records(conn, iin)
    employees = _load_employees(conn, iin)
    missing_inputs, invalid_inputs = _assignment_input_state(assignment_intent)
    blockers: list[dict[str, str]] = []

    def block(code: str, detail: str) -> None:
        if code not in {item["code"] for item in blockers}:
            blockers.append({"code": code, "detail": detail})

    if missing_inputs or invalid_inputs:
        block(
            "ASSIGNMENT_INTENT_INCOMPLETE",
            "Explicit assignment decisions are missing or invalid.",
        )

    selected_import: dict[str, Any] | None = None
    if not import_records:
        block("CONTROL_LIST_RECORD_NOT_FOUND", "No HR control-list row has the exact IIN.")
    if import_selection is None:
        if import_records:
            block("IMPORT_SELECTION_REQUIRED", "Choose one exact import provenance set.")
    else:
        selected_import = _load_import_selection(
            conn, import_selection, iin=iin, block=block
        )

    structural_import_codes = {
        item["code"] for item in blockers
        if item["code"].startswith("IMPORT_") and item["code"] != "IMPORT_SELECTION_REQUIRED"
    }
    business_date = None
    if not missing_inputs and not invalid_inputs and not structural_import_codes:
        business_date = _load_business_date(conn, block=block)

    target_employee: dict[str, Any] | None = None
    if not employees:
        block("EMPLOYEE_NOT_FOUND", "No Employee has this active exact-IIN identity.")
    elif len(employees) != 1:
        block("EMPLOYEE_IIN_CONFLICT", "Exact IIN resolves to multiple Employee identities.")
    else:
        target_employee = employees[0]
        employee_id = int(target_employee["employee_id"])
        if _employee_has_other_active_iin(conn, employee_id, iin):
            block("EMPLOYEE_IIN_CONFLICT", "Employee has a conflicting active IIN identity.")
        if target_employee["operational_status"] != "active":
            block("EMPLOYEE_STATE_NOT_ELIGIBLE", "Employee is not operationally active.")

    resolution = resolve_person_create_or_link_exact_iin_tx(
        conn,
        iin=iin,
        target_employee_id=(
            int(target_employee["employee_id"]) if target_employee is not None else None
        ),
    )
    _resolution_blockers(resolution, block=block)
    candidate_ids = [candidate.person_id for candidate in resolution.candidates]
    assignment_person_ids = set(candidate_ids)
    if target_employee is not None and target_employee["person_id"] is not None:
        assignment_person_ids.add(int(target_employee["person_id"]))
    assignments = _load_primary_assignments(conn, sorted(assignment_person_ids))
    if assignments:
        block("PRIMARY_ASSIGNMENT_EXISTS", "A non-void primary assignment already exists.")

    if selected_import is not None and target_employee is not None:
        employee_id = int(target_employee["employee_id"])
        if selected_import["employee_id"] != employee_id:
            block("IMPORT_ROW_OWNERSHIP_CONFLICT", "Import row belongs to another Employee.")
        if any(
            record["employee_id"] != employee_id
            for record in selected_import["normalized_records"]
        ):
            block(
                "IMPORT_NORMALIZED_RECORD_OWNERSHIP_CONFLICT",
                "A normalized record belongs to another Employee.",
            )

    if not missing_inputs and not invalid_inputs and business_date is not None:
        invalid_inputs.extend(
            value
            for value in _validate_reference_inputs(
                conn,
                assignment_intent,
                business_date=business_date,
                evidence_key_snapshot=evidence_key_snapshot,
                block=block,
            )
            if value not in invalid_inputs
        )
    if assignment_intent is not None and not missing_inputs and not invalid_inputs:
        if assignment_intent.get("reason_code") != "EXISTING_CARD_PERSON_AND_ASSIGNMENT_GAP_CONFIRMED":
            block(
                "REASON_MODE_INCOMPATIBLE",
                "Controlled reason is incompatible with composite existing-card repair.",
            )

    non_classification_blockers = {"IMPORT_SELECTION_REQUIRED"}
    structural_blockers = [
        item for item in blockers if item["code"] not in non_classification_blockers
    ]
    if structural_blockers or resolution.decision not in {"P0_CREATE", "P1_ADOPT"}:
        classification = None
        mode = None
        outcome = None
    else:
        classification = resolution.decision
        mode = COMPOSITE_MODE
        outcome = COMPOSITE_OUTCOME

    public_import_records = [
        {
            "batch_id": record["batch_id"],
            "row_id": record["row_id"],
            "normalized_record_ids": sorted(
                item["normalized_record_id"] for item in record["normalized_records"]
            ),
        }
        for record in import_records
    ]
    public_selected = (
        {
            "batch_id": selected_import["batch_id"],
            "row_id": selected_import["row_id"],
            "normalized_record_ids": sorted(selected_import["normalized_record_ids"]),
        }
        if selected_import is not None
        else None
    )
    return {
        "request_iin": _safe_iin(iin),
        "import_records": public_import_records,
        "selected_import": public_selected,
        "employees": [
            {
                "employee_id": int(row["employee_id"]),
                "person_id": int(row["person_id"]) if row["person_id"] is not None else None,
                "operational_status": row["operational_status"],
                "iin": _safe_iin(row["identity_value"]),
            }
            for row in employees
        ],
        "person_candidates": [
            {
                "person_id": candidate.person_id,
                "person_status": candidate.person_status,
                "compatible": candidate.compatible,
                "incompatibility_reason": (
                    candidate.incompatibility_reasons[0]
                    if candidate.incompatibility_reasons
                    else None
                ),
                "iin": _safe_iin(candidate.iin),
            }
            for candidate in resolution.candidates
        ],
        "primary_assignments": [
            {
                "assignment_id": int(row["assignment_id"]),
                "person_id": int(row["person_id"]),
                "lifecycle_status": row["lifecycle_status"],
                "active_flag": bool(row["active_flag"]),
                "is_primary": bool(row["is_primary"]),
            }
            for row in assignments
        ],
        "classification": classification,
        "mode": mode,
        "proposed_outcome": outcome,
        "blockers": blockers,
        "missing_assignment_inputs": missing_inputs,
        "invalid_assignment_inputs": invalid_inputs,
        "preflight_complete": classification is not None and not blockers,
        "apply_available": False,
        "observed_at": conn.execute(text("SELECT transaction_timestamp()")).scalar_one(),
    }
