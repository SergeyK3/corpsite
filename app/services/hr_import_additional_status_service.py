"""Parse and persist safe, versioned facts from control-list ``Примечание``.

Only an explicit pension or disability statement is interpreted.  The raw note
remains on its import row; it is intentionally neither copied into a fact nor
returned by this service.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import re
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection


POLICY_VERSION = "CONTROL_LIST_NOTE_STATUS_V1"
FACT_DISABILITY = "DISABILITY"
FACT_PENSION = "PENSION"
REVIEW_READY = "AUTO_READY"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
REASON_DATE_MISSING = "STATUS_DATE_MISSING"
REASON_DISABILITY_GROUP_MISSING = "DISABILITY_GROUP_MISSING"
REASON_ICD10_MISSING = "DISABILITY_ICD10_MISSING"
REASON_UNRECOGNIZED = "NOTE_REQUIRES_MANUAL_REVIEW"

_DATE_RE = re.compile(r"(?<!\d)(\d{1,2}[.\-/]\d{1,2}[.\-/](?:19|20)\d{2})(?!\d)")
_ICD10_RE = re.compile(r"\b([A-TV-ZА-Я])\s*(\d{2})(?:[.]\s*([0-9A-ZА-Я]{1,4}))?\b", re.I)
_GROUP_RE = re.compile(r"(?:инвалид(?:ность)?|инв[.]?)\D{0,40}?\b(iii|ii|i|3|2|1)\s*(?:гр(?:упп[аы])?[.]?)?", re.I)
_PENSION_RE = re.compile(r"пенсион", re.I)
_DISABILITY_RE = re.compile(r"инвалид|инв[.]", re.I)
_MATERNITY_RE = re.compile(r"декрет|отпуск\s+по\s+беремен", re.I)


@dataclass(frozen=True)
class ParsedStatusFact:
    fact_kind: str
    effective_date: date | None
    disability_group: str | None
    icd10_code: str | None
    review_status: str
    review_reason: str | None


@dataclass(frozen=True)
class NoteParseResult:
    facts: tuple[ParsedStatusFact, ...]
    requires_manual_review: bool


def _parse_date(value: str) -> date | None:
    match = _DATE_RE.search(value)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1).replace("/", ".").replace("-", "."), "%d.%m.%Y").date()
    except ValueError:
        return None


def _disability_group(value: str) -> str | None:
    match = _GROUP_RE.search(value)
    if not match:
        return None
    normalized = match.group(1).upper()
    return {"1": "I", "2": "II", "3": "III"}.get(normalized, normalized)


def _icd10(value: str) -> str | None:
    match = _ICD10_RE.search(value.upper())
    if not match:
        return None
    letter = match.group(1)
    # Kazakh/Russian keyboard letters are not an ICD code.  Never transliterate
    # an uncertain diagnosis.
    if not ("A" <= letter <= "Z"):
        return None
    suffix = match.group(3)
    return f"{letter}{match.group(2)}" + (f".{suffix}" if suffix else "")


def _reason_for_disability(*, effective_date: date | None, group: str | None, icd10: str | None) -> str | None:
    if effective_date is None:
        return REASON_DATE_MISSING
    if group is None:
        return REASON_DISABILITY_GROUP_MISSING
    if icd10 is None:
        return REASON_ICD10_MISSING
    return None


def parse_control_list_note(value: object) -> NoteParseResult:
    """Classify only explicit source facts; decree wording is deliberately ignored."""
    note = str(value or "").strip()
    if not note:
        return NoteParseResult((), False)

    facts: list[ParsedStatusFact] = []
    has_disability = bool(_DISABILITY_RE.search(note))
    has_pension = bool(_PENSION_RE.search(note))
    effective_date = _parse_date(note)
    if has_disability:
        group = _disability_group(note)
        icd10 = _icd10(note)
        reason = _reason_for_disability(effective_date=effective_date, group=group, icd10=icd10)
        facts.append(
            ParsedStatusFact(
                FACT_DISABILITY,
                effective_date,
                group,
                icd10,
                REVIEW_REQUIRED if reason else REVIEW_READY,
                reason,
            )
        )
    if has_pension:
        reason = None if effective_date else REASON_DATE_MISSING
        facts.append(
            ParsedStatusFact(
                FACT_PENSION,
                effective_date,
                None,
                None,
                REVIEW_REQUIRED if reason else REVIEW_READY,
                reason,
            )
        )

    # A note with no relevant fact and only a maternity/decree reference is
    # intentionally omitted from the personal card.  Any other non-empty note
    # stays visible to HR only as a review-state, without inventing a fact.
    requires_review = bool(note) and not facts and not _MATERNITY_RE.search(note)
    return NoteParseResult(tuple(facts), requires_review)


def _fingerprint(note: str, fact: ParsedStatusFact) -> str:
    safe = "|".join(
        [POLICY_VERSION, fact.fact_kind, str(fact.effective_date or ""), str(fact.disability_group or ""), str(fact.icd10_code or ""), note]
    )
    return sha256(safe.encode("utf-8")).hexdigest()


def _fact_table_exists(conn: Connection) -> bool:
    return conn.execute(text("SELECT to_regclass('public.person_status_facts') IS NOT NULL")).scalar_one()


def persist_control_list_note_facts(conn: Connection, *, batch_id: int) -> dict[str, int]:
    """Create only missing initial fact versions for matched import rows.

    No raw note is copied into the facts table.  The batch/row FK retains
    provenance, while a source fingerprint makes reruns stable and auditable.
    """
    if not _fact_table_exists(conn):
        raise RuntimeError("person_status_facts schema is not installed")
    rows = conn.execute(
        text(
            """
            SELECT r.row_id, r.employee_id, r.normalized_payload->>'note_raw' AS note,
                   e.person_id
            FROM public.hr_import_rows r
            JOIN public.employees e ON e.employee_id=r.employee_id
            WHERE r.batch_id=:batch_id AND r.employee_id IS NOT NULL
            """
        ),
        {"batch_id": int(batch_id)},
    ).mappings().all()
    result = {"source_rows": 0, "created": 0, "ready": 0, "review_required": 0, "ignored_maternity": 0}
    for row in rows:
        parsed = parse_control_list_note(row["note"])
        if not parsed.facts and not parsed.requires_manual_review:
            if str(row["note"] or "").strip():
                result["ignored_maternity"] += 1
            continue
        result["source_rows"] += 1
        for fact in parsed.facts:
            source_fingerprint = _fingerprint(str(row["note"] or ""), fact)
            inserted = conn.execute(
                text(
                    """
                    INSERT INTO public.person_status_facts(
                        person_id, employee_context_id, fact_kind, effective_date,
                        disability_group, icd10_code, review_status, review_reason,
                        source_batch_id, source_row_id, source_policy_version,
                        source_fingerprint, version
                    )
                    SELECT :person_id, :employee_id, :fact_kind, :effective_date,
                           :disability_group, :icd10_code, :review_status, :review_reason,
                           :batch_id, :row_id, :policy_version, :source_fingerprint, 1
                    WHERE NOT EXISTS (
                        SELECT 1 FROM public.person_status_facts
                        WHERE source_row_id=:row_id AND fact_kind=:fact_kind AND version=1
                    )
                    """
                ),
                {
                    "person_id": int(row["person_id"]), "employee_id": int(row["employee_id"]),
                    "fact_kind": fact.fact_kind, "effective_date": fact.effective_date,
                    "disability_group": fact.disability_group, "icd10_code": fact.icd10_code,
                    "review_status": fact.review_status, "review_reason": fact.review_reason,
                    "batch_id": int(batch_id), "row_id": int(row["row_id"]),
                    "policy_version": POLICY_VERSION, "source_fingerprint": source_fingerprint,
                },
            )
            if inserted.rowcount:
                result["created"] += 1
                result["ready" if fact.review_status == REVIEW_READY else "review_required"] += 1
    return result


def current_status_fact_rows(conn: Connection, *, employee_ids: Iterable[int] | None = None) -> list[dict]:
    """Read latest fact version per source kind; never returns source note text."""
    if not _fact_table_exists(conn):
        return []
    params: dict[str, object] = {}
    employee_clause = ""
    if employee_ids is not None:
        ids = [int(value) for value in employee_ids]
        if not ids:
            return []
        params["employee_ids"] = ids
        employee_clause = " AND f.employee_context_id = ANY(:employee_ids)"
    return [
        dict(row)
        for row in conn.execute(
            text(
                """
                SELECT f.status_fact_id, f.person_id, f.employee_context_id, f.fact_kind,
                       f.effective_date, f.disability_group, f.icd10_code,
                       f.review_status, f.review_reason, f.source_batch_id,
                       f.source_row_id, f.version, f.created_at
                FROM public.person_status_facts f
                WHERE NOT EXISTS (
                    SELECT 1 FROM public.person_status_facts newer
                    WHERE newer.supersedes_fact_id=f.status_fact_id
                )
                """ + employee_clause + " ORDER BY f.person_id, f.fact_kind, f.version"
            ),
            params,
        ).mappings().all()
    ]


def correct_status_fact(
    conn: Connection,
    *,
    status_fact_id: int,
    effective_date: date | None,
    disability_group: str | None,
    icd10_code: str | None,
    review_status: str,
    review_reason: str | None,
    actor_user_id: int,
    correction_reason: str,
) -> int:
    """Append a correction version; existing import facts are never updated."""
    parent = conn.execute(
        text("SELECT * FROM public.person_status_facts WHERE status_fact_id=:fact_id FOR KEY SHARE"),
        {"fact_id": int(status_fact_id)},
    ).mappings().one()
    next_version = int(parent["version"]) + 1
    fact_id = conn.execute(
        text(
            """
            INSERT INTO public.person_status_facts(
              person_id, employee_context_id, fact_kind, effective_date, disability_group,
              icd10_code, review_status, review_reason, source_batch_id, source_row_id,
              source_policy_version, source_fingerprint, supersedes_fact_id, version,
              correction_reason, created_by_user_id
            ) VALUES (
              :person_id,:employee_id,:fact_kind,:effective_date,:disability_group,
              :icd10_code,:review_status,:review_reason,:batch_id,:row_id,
              :policy_version,:source_fingerprint,:parent_id,:version,:correction_reason,:actor
            ) RETURNING status_fact_id
            """
        ),
        {
            "person_id": parent["person_id"], "employee_id": parent["employee_context_id"],
            "fact_kind": parent["fact_kind"], "effective_date": effective_date,
            "disability_group": disability_group, "icd10_code": icd10_code,
            "review_status": review_status, "review_reason": review_reason,
            "batch_id": parent["source_batch_id"], "row_id": parent["source_row_id"],
            "policy_version": POLICY_VERSION,
            "source_fingerprint": sha256(f"{parent['source_fingerprint']}|{next_version}".encode()).hexdigest(),
            "parent_id": int(status_fact_id), "version": next_version,
            "correction_reason": correction_reason, "actor": int(actor_user_id),
        },
    ).scalar_one()
    return int(fact_id)
