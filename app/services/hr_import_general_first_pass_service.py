"""Idempotent first-pass completion of the Person general-information fields.

The worker deliberately uses no name matching.  It operates only on a Person
already linked to an active Employee and records a PII-free event describing
the outcome.  A caller owns the transaction.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection



POLICY_VERSION = "HR_IMPORT_GENERAL_FIRST_PASS_V1"
EVENT_AUTO_READY = "HR_IMPORT_GENERAL_AUTO_READY"
EVENT_REVIEW_REQUIRED = "HR_IMPORT_GENERAL_REVIEW_REQUIRED"
STATUS_AUTO_READY = "AUTO_READY"
STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
REASON_COMPLETED = "RUN_PREVIEW_READY"
REASON_NAME_PARSE = "CONFLICT_NAME_PARSE"


@dataclass(frozen=True)
class NameParts:
    last_name: str
    first_name: str
    middle_name: str | None


@dataclass(frozen=True)
class GeneralFirstPassResult:
    processed: int
    review_required: int
    updated: int
    skipped_already_filled: int


def _normalized_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _is_name_token(value: str) -> bool:
    return bool(value) and all(character.isalpha() or character in "-'" for character in value)


def parse_full_name(value: Any) -> tuple[NameParts | None, str | None]:
    """Parse only the established surname → name → patronymic form.

    Two tokens are valid when the source has no patronymic.  Four or more
    components have no safe, project-approved disambiguation rule and are
    explicitly left for HR review.
    """
    parts = _normalized_text(value).split(" ")
    if len(parts) not in (2, 3):
        return None, "NAME_COMPONENT_COUNT_UNCERTAIN"
    if not all(_is_name_token(part) for part in parts):
        return None, "NAME_COMPONENTS_INVALID"
    return NameParts(parts[0], parts[1], parts[2] if len(parts) == 3 else None), None


def _separate_source_parts(payload: dict[str, Any]) -> NameParts | None:
    last_name = _normalized_text(payload.get("last_name") or payload.get("surname"))
    first_name = _normalized_text(payload.get("first_name") or payload.get("given_name"))
    middle_name = _normalized_text(payload.get("middle_name") or payload.get("patronymic")) or None
    if not last_name or not first_name:
        return None
    if not _is_name_token(last_name) or not _is_name_token(first_name):
        return None
    if middle_name is not None and not _is_name_token(middle_name):
        return None
    return NameParts(last_name, first_name, middle_name)


def surname_alphabet(value: str | None) -> str:
    """First letter of a surname, retaining Kazakh/Cyrillic characters."""
    for character in str(value or "").lstrip():
        if character.isalpha():
            return character.upper()
    return ""


def _safe_fingerprint(*, person_id: int, source_name: str, source_parts: NameParts | None) -> str:
    payload = {
        "person_id": int(person_id),
        "source_name_sha256": hashlib.sha256(source_name.encode("utf-8")).hexdigest(),
        "source_parts": bool(source_parts),
        "policy_version": POLICY_VERSION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _latest_is_same_outcome(
    conn: Connection,
    *,
    person_id: int,
    event_type: str,
    input_fingerprint: str,
) -> bool:
    return conn.execute(
        text(
            f"""
            SELECT 1
            FROM public.personnel_record_events
            WHERE person_id = :person_id
              AND event_type = :event_type
              AND event_payload ->> 'policy_version' = :policy_version
              AND event_payload ->> 'input_fingerprint' = :input_fingerprint
            LIMIT 1
            """
        ),
        {
            "person_id": int(person_id),
            "event_type": event_type,
            "policy_version": POLICY_VERSION,
            "input_fingerprint": input_fingerprint,
        },
    ).scalar_one_or_none() is not None


def _event_timestamp_column(conn: Connection) -> str:
    """Support the local pre-PPR-R3 journal and the current journal schema."""
    names = set(
        conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'personnel_record_events'
                  AND column_name IN ('event_at', 'occurred_at')
                """
            )
        ).scalars()
    )
    if "occurred_at" in names:
        return "occurred_at"
    if "event_at" in names:
        return "event_at"
    raise RuntimeError("personnel_record_events has no event timestamp column")


def _ensure_general_information_domain(conn: Connection) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.personnel_migration_domains(
                domain_code, display_name, description, is_enabled,
                target_table_names, control_list_columns
            )
            VALUES(
                'general_information', 'General information',
                'Idempotent HR-import first-pass completion of Person name fields',
                TRUE, '["persons"]'::jsonb, '["full_name"]'::jsonb
            )
            ON CONFLICT (domain_code) DO NOTHING
            """
        )
    )


def _start_run(conn: Connection) -> int:
    """Create the durable, PII-free envelope for one first-pass execution."""
    _ensure_general_information_domain(conn)
    return int(
        conn.execute(
            text(
                """
                INSERT INTO public.personnel_migration_runs(
                    domain_code, run_status, started_by, metadata
                )
                VALUES(
                    'general_information', 'draft',
                    'system:hr-import-general-first-pass',
                    CAST(:metadata AS jsonb)
                )
                RETURNING run_id
                """
            ),
            {
                "metadata": json.dumps(
                    {"general_first_pass": {"policy_version": POLICY_VERSION}},
                    ensure_ascii=False,
                )
            },
        ).scalar_one()
    )


def _finish_run(conn: Connection, *, run_id: int, result: GeneralFirstPassResult) -> None:
    conn.execute(
        text(
            """
            UPDATE public.personnel_migration_runs
            SET run_status='committed', committed_at=NOW(),
                committed_by='system:hr-import-general-first-pass',
                metadata=CAST(:metadata AS jsonb)
            WHERE run_id=:run_id AND run_status='draft'
            """
        ),
        {
            "run_id": int(run_id),
            "metadata": json.dumps(
                {
                    "general_first_pass": {
                        "policy_version": POLICY_VERSION,
                        "processed": result.processed,
                        "review_required": result.review_required,
                        "updated": result.updated,
                        "skipped_already_filled": result.skipped_already_filled,
                    }
                },
                ensure_ascii=False,
            ),
        },
    )


def _record_outcome(
    conn: Connection,
    *,
    person_id: int,
    employee_id: int,
    event_type: str,
    status_code: str,
    reason_code: str,
    input_fingerprint: str,
    changed_fields: list[str],
    migration_run_id: int,
) -> None:
    if _latest_is_same_outcome(
        conn,
        person_id=person_id,
        event_type=event_type,
        input_fingerprint=input_fingerprint,
    ):
        return
    timestamp_column = _event_timestamp_column(conn)
    conn.execute(
        text(
            f"""
            INSERT INTO public.personnel_record_events(
                person_id, employee_context_id, domain_code, record_table_name,
                record_id, event_type, {timestamp_column}, actor_id, event_payload,
                migration_run_id
            )
            VALUES(
                :person_id, :employee_id, 'general_information', 'persons',
                :person_id, :event_type, NOW(), :actor_id, CAST(:event_payload AS jsonb),
                :migration_run_id
            )
            """
        ),
        {
            "person_id": person_id,
            "employee_id": employee_id,
            "event_type": event_type,
            "actor_id": "system:hr-import-general-first-pass",
            "migration_run_id": int(migration_run_id),
            # No source FIO or other raw identity value is written to the event.
            "event_payload": json.dumps(
                {
                    "policy_version": POLICY_VERSION,
                    "status_code": status_code,
                    "reason_code": reason_code,
                    "input_fingerprint": input_fingerprint,
                    "changed_fields": sorted(changed_fields),
                },
                ensure_ascii=False,
            ),
        },
    )


def run_general_first_pass(
    conn: Connection,
    *,
    employee_ids: list[int] | None = None,
) -> GeneralFirstPassResult:
    """Fill absent name parts for all current active employee/person pairs.

    Existing separate Person fields always win.  The run is idempotent: an
    unchanged source produces neither a second event nor a second update.
    """
    scoped_employee_ids = sorted({int(employee_id) for employee_id in employee_ids or []})
    run_id = _start_run(conn)
    scope_clause = "AND e.employee_id = ANY(:employee_ids)" if scoped_employee_ids else ""
    rows = conn.execute(
        text(
            f"""
            SELECT e.employee_id, p.person_id, p.full_name, p.last_name,
                   p.first_name, p.middle_name,
                   imported.normalized_payload AS source_payload
            FROM public.employees e
            JOIN public.persons p ON p.person_id = e.person_id
            LEFT JOIN LATERAL (
                SELECT r.normalized_payload
                FROM public.hr_import_rows r
                WHERE r.batch_id = 1414
                  AND r.employee_id = e.employee_id
                ORDER BY r.row_id DESC
                LIMIT 1
            ) imported ON TRUE
            WHERE COALESCE(e.is_active, TRUE) IS TRUE
              AND e.operational_status = 'active'
              AND (e.date_from IS NULL OR e.date_from <= CURRENT_DATE)
              AND (e.date_to IS NULL OR e.date_to >= CURRENT_DATE)
              AND p.person_status = 'active'
              {scope_clause}
            ORDER BY e.employee_id
            FOR UPDATE OF p
            """
        ),
        {"employee_ids": scoped_employee_ids} if scoped_employee_ids else {},
    ).mappings()
    processed = review_required = updated = skipped_already_filled = 0
    for row in rows:
        person_id = int(row["person_id"])
        employee_id = int(row["employee_id"])
        source_payload = dict(row["source_payload"] or {})
        source_name = _normalized_text(source_payload.get("full_name") or row["full_name"])
        parsed = _separate_source_parts(source_payload)
        if parsed is None:
            parsed, parse_reason = parse_full_name(source_name)
        else:
            parse_reason = None
        existing = {
            "last_name": _normalized_text(row["last_name"]) or None,
            "first_name": _normalized_text(row["first_name"]) or None,
            "middle_name": _normalized_text(row["middle_name"]) or None,
        }
        input_fingerprint = _safe_fingerprint(
            person_id=person_id,
            source_name=source_name,
            source_parts=parsed,
        )
        if parsed is None:
            # A pre-existing complete set remains valid; only absent fields
            # make an ambiguous full name a review item.
            if existing["last_name"] and existing["first_name"]:
                _record_outcome(
                    conn, person_id=person_id, employee_id=employee_id,
                    event_type=EVENT_AUTO_READY, status_code=STATUS_AUTO_READY,
                    reason_code=REASON_COMPLETED, input_fingerprint=input_fingerprint,
                    changed_fields=[], migration_run_id=run_id,
                )
                processed += 1
                skipped_already_filled += 1
            else:
                _record_outcome(
                    conn, person_id=person_id, employee_id=employee_id,
                    event_type=EVENT_REVIEW_REQUIRED, status_code=STATUS_REVIEW_REQUIRED,
                    reason_code=REASON_NAME_PARSE, input_fingerprint=input_fingerprint,
                    changed_fields=[], migration_run_id=run_id,
                )
                review_required += 1
            continue
        source_parts = {
            "last_name": parsed.last_name,
            "first_name": parsed.first_name,
            "middle_name": parsed.middle_name,
        }
        changes = {
            field: value
            for field, value in source_parts.items()
            if value and existing[field] is None
        }
        if changes:
            conn.execute(
                text(
                    """
                    UPDATE public.persons
                    SET last_name = COALESCE(NULLIF(BTRIM(last_name), ''), :last_name),
                        first_name = COALESCE(NULLIF(BTRIM(first_name), ''), :first_name),
                        middle_name = COALESCE(NULLIF(BTRIM(middle_name), ''), :middle_name),
                        updated_at = NOW()
                    WHERE person_id = :person_id
                    """
                ),
                {
                    "person_id": person_id,
                    "last_name": source_parts["last_name"],
                    "first_name": source_parts["first_name"],
                    "middle_name": source_parts["middle_name"],
                },
            )
            updated += 1
        else:
            skipped_already_filled += 1
        _record_outcome(
            conn, person_id=person_id, employee_id=employee_id,
            event_type=EVENT_AUTO_READY, status_code=STATUS_AUTO_READY,
            reason_code=REASON_COMPLETED, input_fingerprint=input_fingerprint,
            changed_fields=list(changes), migration_run_id=run_id,
        )
        processed += 1
    result = GeneralFirstPassResult(
        processed=processed,
        review_required=review_required,
        updated=updated,
        skipped_already_filled=skipped_already_filled,
    )
    _finish_run(conn, run_id=run_id, result=result)
    return result


def general_first_pass_statuses(conn: Connection, *, person_ids: list[int]) -> dict[int, dict[str, Any]]:
    """Latest persisted first-pass outcome for UI/status projections."""
    if not person_ids:
        return {}
    timestamp_column = _event_timestamp_column(conn)
    rows = conn.execute(
        text(
            f"""
            SELECT DISTINCT ON (person_id) person_id, event_type, event_payload
            FROM public.personnel_record_events
            WHERE person_id = ANY(:person_ids)
              AND event_type IN (:ready, :review)
              AND event_payload ->> 'policy_version' = :policy_version
            ORDER BY person_id, {timestamp_column} DESC, event_id DESC
            """
        ),
        {
            "person_ids": [int(value) for value in person_ids],
            "ready": EVENT_AUTO_READY,
            "review": EVENT_REVIEW_REQUIRED,
            "policy_version": POLICY_VERSION,
        },
    ).mappings()
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        payload = dict(row["event_payload"] or {})
        reason_code = str(payload.get("reason_code") or REASON_NAME_PARSE)
        # The first local invocation used an internal run-state name before
        # the established report-reason catalog was applied.  Preserve the
        # immutable event and expose its equivalent catalog reason.
        if reason_code == "RUN_COMPLETED_PENDING_REVIEW":
            reason_code = REASON_COMPLETED
        result[int(row["person_id"])] = {
            "status_code": str(payload.get("status_code") or STATUS_REVIEW_REQUIRED),
            "reason_code": reason_code,
            "changed_field_count": len(payload.get("changed_fields") or []),
        }
    return result


def general_first_pass_run_summary(conn: Connection) -> dict[str, int] | None:
    """Return counters for the last committed first-pass invocation.

    The run envelope intentionally outlives the request that made it, while
    individual Person events remain immutable and are not duplicated on a
    no-op retry.
    """
    row = conn.execute(
        text(
            """
            SELECT metadata -> 'general_first_pass' AS summary
            FROM public.personnel_migration_runs
            WHERE domain_code='general_information'
              AND run_status='committed'
              AND metadata -> 'general_first_pass' ->> 'policy_version' = :policy_version
            ORDER BY committed_at DESC NULLS LAST, run_id DESC
            LIMIT 1
            """
        ),
        {"policy_version": POLICY_VERSION},
    ).mappings().first()
    if not row:
        return None
    summary = dict(row["summary"] or {})
    return {
        "processed": int(summary.get("processed") or 0),
        "review_required": int(summary.get("review_required") or 0),
        "updated_current_run": int(summary.get("updated") or 0),
        "skipped_already_filled": int(summary.get("skipped_already_filled") or 0),
    }
