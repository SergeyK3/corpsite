"""Append-only HR corrections for structured pension and disability facts.

The event journal records only that a correction occurred and row counts.  It
never receives diagnosis codes, disability groups, dates, or source note text.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import re

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.personnel_record_event_service import emit_personnel_record_event


class NoteFactVersionConflict(RuntimeError):
    """The card was changed after the editor loaded it."""


_ICD10_RE = re.compile(r"^[A-TV-Z][0-9]{2}(?:\.[0-9A-Z]{1,4})?$")
_PENSION_KINDS = {"AGE", "SERVICE"}
_DISABILITY_GROUPS = {"I", "II", "III"}
_POLICY = "PPR_ADDITIONAL_HR_CORRECTION_V1"


def _optional_date(value: object) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("effective_date must be a complete ISO date") from exc


def _current_facts(conn: Connection, *, person_id: int) -> dict[int, dict]:
    rows = conn.execute(
        text(
            """
            SELECT * FROM public.person_status_facts f
            WHERE f.person_id=:person_id AND NOT f.is_deleted
              AND NOT EXISTS (
                SELECT 1 FROM public.person_status_facts newer
                WHERE newer.supersedes_fact_id=f.status_fact_id
              )
            FOR UPDATE
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().all()
    return {int(row["status_fact_id"]): dict(row) for row in rows}


def _source_for_new_fact(conn: Connection, *, employee_id: int) -> dict:
    row = conn.execute(
        text(
            """
            SELECT row_id, batch_id
            FROM public.hr_import_rows
            WHERE employee_id=:employee_id
            ORDER BY row_id DESC
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().one_or_none()
    if row is None:
        raise ValueError("an HR import row is required before adding a status fact")
    return dict(row)


def _safe_fingerprint(*, person_id: int, fact_kind: str, source_row_id: int, version: int, parent_id: int | None, entry_key: str = "") -> str:
    # Do not derive an audit/provenance hash from medical values or free text.
    material = f"{_POLICY}|{person_id}|{fact_kind}|{source_row_id}|{version}|{parent_id or 0}|{entry_key}"
    return sha256(material.encode("utf-8")).hexdigest()


def _normalize_row(kind: str, row: dict) -> dict:
    effective_date = _optional_date(row.get("effective_date"))
    if kind == "PENSION":
        pension_kind = str(row.get("pension_kind") or "").strip().upper() or None
        if pension_kind and pension_kind not in _PENSION_KINDS:
            raise ValueError("pension_kind must be AGE or SERVICE")
        reason = None if pension_kind and effective_date else "PENSION_DETAILS_INCOMPLETE"
        return {
            "effective_date": effective_date,
            "disability_group": None,
            "icd10_code": None,
            "pension_kind": pension_kind,
            "review_status": "AUTO_READY" if reason is None else "REVIEW_REQUIRED",
            "review_reason": reason,
        }

    group = str(row.get("disability_group") or "").strip().upper() or None
    icd10 = str(row.get("icd10_code") or "").strip().upper() or None
    if group and group not in _DISABILITY_GROUPS:
        raise ValueError("disability_group must be I, II or III")
    if icd10 and not _ICD10_RE.fullmatch(icd10):
        raise ValueError("icd10_code must be a valid ICD-10 code")
    reason = None if group and effective_date and icd10 else "DISABILITY_DETAILS_INCOMPLETE"
    return {
        "effective_date": effective_date,
        "disability_group": group,
        "icd10_code": icd10,
        "pension_kind": None,
        "review_status": "AUTO_READY" if reason is None else "REVIEW_REQUIRED",
        "review_reason": reason,
    }


def _append(conn: Connection, *, parent: dict | None, source: dict, person_id: int, employee_id: int, kind: str, values: dict, actor_id: int, is_deleted: bool = False, entry_key: str = "") -> int:
    version = (int(parent["version"]) + 1) if parent else 1
    parent_id = int(parent["status_fact_id"]) if parent else None
    row = conn.execute(
        text(
            """
            INSERT INTO public.person_status_facts(
              person_id, employee_context_id, fact_kind, effective_date,
              disability_group, icd10_code, pension_kind, review_status, review_reason,
              source_batch_id, source_row_id, source_policy_version, source_fingerprint,
              supersedes_fact_id, version, correction_reason, created_by_user_id, is_deleted
            ) VALUES (
              :person_id,:employee_id,:fact_kind,:effective_date,
              :disability_group,:icd10_code,:pension_kind,:review_status,:review_reason,
              :batch_id,:row_id,:policy,:fingerprint,:parent_id,:version,
              'HR_CORRECTION',:actor_id,:is_deleted
            ) RETURNING status_fact_id
            """
        ),
        {
            "person_id": int(person_id), "employee_id": int(employee_id), "fact_kind": kind,
            "effective_date": values["effective_date"], "disability_group": values["disability_group"],
            "icd10_code": values["icd10_code"], "pension_kind": values["pension_kind"],
            "review_status": values["review_status"], "review_reason": values["review_reason"],
            "batch_id": int(source["batch_id"]), "row_id": int(source["row_id"]), "policy": _POLICY,
            "fingerprint": _safe_fingerprint(person_id=person_id, fact_kind=kind, source_row_id=int(source["row_id"]), version=version, parent_id=parent_id, entry_key=entry_key),
            "parent_id": parent_id, "version": version, "actor_id": int(actor_id), "is_deleted": bool(is_deleted),
        },
    ).scalar_one()
    return int(row)


def _unchanged(parent: dict, values: dict) -> bool:
    return all(
        parent.get(key) == values.get(key)
        for key in ("effective_date", "disability_group", "icd10_code", "pension_kind", "review_status", "review_reason")
    )


def save_note_facts(
    conn: Connection, *, person_id: int, employee_id: int, pension_rows: list[dict], disability_rows: list[dict],
    expected_fact_ids: list[int], actor_id: int,
) -> dict[str, int]:
    """Persist the two card tables as append-only corrections with optimistic checks."""
    current = _current_facts(conn, person_id=person_id)
    if {int(value) for value in expected_fact_ids} != set(current):
        raise NoteFactVersionConflict()
    submitted_ids: set[int] = set()
    inserted = deleted = 0

    for kind, rows in (("PENSION", pension_rows), ("DISABILITY", disability_rows)):
        for row_index, submitted in enumerate(rows):
            if not isinstance(submitted, dict):
                raise ValueError("status-fact rows must be objects")
            fact_id = submitted.get("status_fact_id")
            parent = None
            if fact_id is not None:
                parent = current.get(int(fact_id))
                if parent is None or parent["fact_kind"] != kind:
                    raise NoteFactVersionConflict()
                if int(submitted.get("version") or 0) != int(parent["version"]):
                    raise NoteFactVersionConflict()
                submitted_ids.add(int(fact_id))
                source = {"row_id": parent["source_row_id"], "batch_id": parent["source_batch_id"]}
            else:
                source = _source_for_new_fact(conn, employee_id=employee_id)
            values = _normalize_row(kind, submitted)
            if parent is not None and _unchanged(parent, values):
                continue
            _append(
                conn, parent=parent, source=source, person_id=person_id, employee_id=employee_id,
                kind=kind, values=values, actor_id=actor_id, entry_key=str(row_index),
            )
            inserted += 1

    # A missing current row was deliberately removed in the submitted table.
    for fact_id, parent in current.items():
        if fact_id in submitted_ids:
            continue
        source = {"row_id": parent["source_row_id"], "batch_id": parent["source_batch_id"]}
        values = {
            "effective_date": parent["effective_date"], "disability_group": parent["disability_group"],
            "icd10_code": parent["icd10_code"], "pension_kind": parent.get("pension_kind"),
            "review_status": parent["review_status"], "review_reason": parent["review_reason"],
        }
        _append(conn, parent=parent, source=source, person_id=person_id, employee_id=employee_id,
                kind=str(parent["fact_kind"]), values=values, actor_id=actor_id, is_deleted=True)
        deleted += 1

    emit_personnel_record_event(
        conn, person_id=person_id, employee_context_id=employee_id, domain_code="additional",
        record_table_name="person_status_facts", record_id=person_id,
        event_type="PPR_ADDITIONAL_STATUS_FACTS_HR_CORRECTED", actor_id=str(actor_id),
        event_payload={
            "operation": "HR_CORRECTION", "pension_rows": len(pension_rows),
            "disability_rows": len(disability_rows), "deleted_rows": deleted,
        },
    )
    return {"created_versions": inserted, "deleted_versions": deleted}
