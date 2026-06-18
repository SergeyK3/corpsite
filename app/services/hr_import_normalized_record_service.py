"""Populate hr_import_normalized_records from merged import profile + candidates (ADR-039 Phase 3C)."""
from __future__ import annotations

import hashlib
import re
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.hr_import_analytics_service import (
    BatchNotFoundError,
    _ensure_batch_exists,
    is_real_employee_row,
)
from app.services.hr_import_document_parser import VALID_UNTIL_RE, _parse_dmy
from app.services.hr_import_education_profile_service import (
    _load_effective_profile_meta,
    _resolve_merged_profile,
)
from scripts.import_hr_control_list import mask_iin

REVIEW_STATUS_PENDING = "pending"
REVIEW_STATUS_APPROVED = "approved"
REVIEW_STATUS_REJECTED = "rejected"
REVIEW_STATUS_PROMOTED = "promoted"
REVIEW_STATUS_SUPERSEDED = "superseded"

RECORD_KIND_TRAINING = "training"
RECORD_KIND_CERTIFICATE = "certificate"
RECORD_KIND_CATEGORY = "category"
RECORD_KIND_EDUCATION = "education"

REVIEW_STATUSES = frozenset(
    {
        REVIEW_STATUS_PENDING,
        REVIEW_STATUS_APPROVED,
        REVIEW_STATUS_REJECTED,
        REVIEW_STATUS_PROMOTED,
        REVIEW_STATUS_SUPERSEDED,
    }
)

ALLOWED_REVIEW_TRANSITIONS: dict[str, frozenset[str]] = {
    REVIEW_STATUS_PENDING: frozenset({REVIEW_STATUS_APPROVED, REVIEW_STATUS_REJECTED}),
    REVIEW_STATUS_APPROVED: frozenset({REVIEW_STATUS_PENDING}),
    REVIEW_STATUS_REJECTED: frozenset({REVIEW_STATUS_PENDING}),
    REVIEW_STATUS_PROMOTED: frozenset(),
    REVIEW_STATUS_SUPERSEDED: frozenset(),
}

RECORD_KINDS = frozenset(
    {
        RECORD_KIND_TRAINING,
        RECORD_KIND_CERTIFICATE,
        RECORD_KIND_CATEGORY,
        RECORD_KIND_EDUCATION,
    }
)

PROPOSED_TO_DOCUMENT_TYPE_CODE: dict[str, Optional[str]] = {
    "TRAINING_HOURS": "CONTINUING_EDUCATION",
    "QUAL_UPGRADE": "CONTINUING_EDUCATION",
    "SEMINAR_CERT": "SEMINAR_PARTICIPATION",
    "CONFERENCE_CERT": "CONFERENCE_PARTICIPATION",
    "WORKSHOP_CERT": "MASTERCLASS_PARTICIPATION",
    "NMO": "CONTINUING_EDUCATION",
    "COURSE": "CONTINUING_EDUCATION",
    "EDUCATION_GRADUATION": "EDUCATION_GRADUATION",
    "SPECIALIST_CERT": "SPECIALIST_CERTIFICATION",
    "QUALIFICATION_CATEGORY": None,
}

DEFAULT_DOCUMENT_TYPE_CODE: dict[str, Optional[str]] = {
    RECORD_KIND_TRAINING: "CONTINUING_EDUCATION",
    RECORD_KIND_CERTIFICATE: "SPECIALIST_CERTIFICATION",
    RECORD_KIND_CATEGORY: None,
    RECORD_KIND_EDUCATION: "EDUCATION_GRADUATION",
}


def normalized_records_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'hr_import_normalized_records'
            """
        )
    ).first()
    return row is not None


def norm_title(value: str) -> str:
    text_val = (value or "").strip().lower().replace("ё", "е")
    return " ".join(text_val.split())


def norm_source_text(value: str) -> str:
    return " ".join((value or "").strip().split())


def compute_source_record_key(
    *,
    row_id: int,
    employee_id: Optional[int],
    record_kind: str,
    title: str,
    issue_date: Optional[date],
    end_date: Optional[date],
    hours: Optional[int],
    document_number: str,
    source_field: str,
    fragment_index: int,
) -> str:
    """Deterministic dedup key per ADR-039 Phase 3B §4."""
    scope = f"emp:{employee_id}" if employee_id is not None else f"row:{row_id}"

    def _date_str(value: Optional[date]) -> str:
        return value.isoformat() if value else ""

    def _hours_str(value: Optional[int]) -> str:
        return str(value) if value is not None else ""

    canonical = "|".join(
        [
            scope,
            record_kind,
            norm_title(title),
            _date_str(issue_date),
            _date_str(end_date),
            _hours_str(hours),
            (document_number or "").strip(),
            (source_field or "").strip(),
            str(fragment_index),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _coerce_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text_val = str(value).strip()
    if not text_val:
        return None
    if re.fullmatch(r"\d{4}", text_val):
        return date(int(text_val), 1, 1)
    try:
        return date.fromisoformat(text_val[:10])
    except ValueError:
        return None


def _coerce_hours(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        hours = int(float(value))
    except (TypeError, ValueError):
        return None
    return hours if hours >= 0 else None


def _coerce_confidence(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score < 0 or score > 1:
        return None
    return round(score, 4)


def _parse_category_expiry_from_text(text: str) -> Optional[date]:
    """Category validity end date from «до DD.MM.YYYY» in source text."""
    match = VALID_UNTIL_RE.search(text or "")
    if not match:
        return None
    return _parse_dmy(match.group(1))


def _resolve_category_issue_expiry_dates(
    record: dict[str, Any],
    enrichment: dict[str, Any],
    source_text: str,
) -> tuple[Optional[date], Optional[date]]:
    """
    Category rows: expiry from «до …»; issue_date only when profile issued_at is
    strictly before category expiry. Never borrow certificate issue dates from enrichment.
    """
    expiry_date = _parse_category_expiry_from_text(source_text)
    if expiry_date is None:
        expiry_date = _coerce_date(enrichment.get("parsed_valid_until"))

    issue_date = None
    record_issued = _coerce_date(record.get("issued_at"))
    if record_issued is not None and expiry_date is not None and record_issued < expiry_date:
        issue_date = record_issued

    if issue_date is not None and expiry_date is not None and issue_date > expiry_date:
        issue_date = None

    return issue_date, expiry_date


def _resolve_document_type_code(
    record_kind: str,
    *,
    proposed_code: Optional[str],
) -> Optional[str]:
    if proposed_code:
        mapped = PROPOSED_TO_DOCUMENT_TYPE_CODE.get(proposed_code)
        if mapped is not None:
            return mapped
        if proposed_code in PROPOSED_TO_DOCUMENT_TYPE_CODE.values():
            return proposed_code
    return DEFAULT_DOCUMENT_TYPE_CODE.get(record_kind)


def _load_document_type_ids(conn: Connection) -> dict[str, int]:
    rows = conn.execute(
        text(
            """
            SELECT code, document_type_id
            FROM public.document_types
            WHERE is_active = TRUE
            """
        )
    ).mappings().all()
    return {str(row["code"]): int(row["document_type_id"]) for row in rows}


def _load_rows_for_population(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    _ensure_batch_exists(conn, batch_id)
    db_rows = conn.execute(
        text(
            """
            SELECT row_id, employee_id, normalized_payload
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
            ORDER BY row_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()

    items: list[dict[str, Any]] = []
    for db_row in db_rows:
        payload = dict(db_row["normalized_payload"] or {})
        metadata = dict(payload.pop("metadata", {}) or {})
        sheet_type = str(metadata.get("sheet_type", "") or "")
        classification = str(metadata.get("classification", "") or "")
        row_type = str(metadata.get("row_type", "") or "")
        is_employee_roster = bool(metadata.get("is_employee_roster", row_type == "employee"))
        analytics_row = {
            "sheet_type": sheet_type,
            "classification": classification,
            "row_type": row_type,
            "is_employee_roster": is_employee_roster,
            "iin": str(payload.get("iin", "") or "").strip(),
        }
        if not is_real_employee_row(analytics_row):
            continue
        items.append(
            {
                "row_id": int(db_row["row_id"]),
                "batch_id": batch_id,
                "employee_id": int(db_row["employee_id"]) if db_row["employee_id"] else None,
                "payload": payload,
            }
        )
    return items


def _load_candidate_enrichment(conn: Connection, batch_id: int) -> dict[tuple[Any, ...], dict[str, Any]]:
    if not conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'hr_import_document_candidates'
            """
        )
    ).first():
        return {}

    rows = conn.execute(
        text(
            """
            SELECT
                row_id,
                source_field,
                raw_text,
                fragment_index,
                proposed_document_type,
                parsed_valid_until,
                parsed_issued_at,
                parsed_hours,
                certificate_number,
                organization,
                title,
                specialty,
                parse_method,
                confidence_score
            FROM public.hr_import_document_candidates
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()

    index: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        row_id = int(row["row_id"])
        source_field = str(row.get("source_field") or "")
        raw_text = str(row.get("raw_text") or "")
        fragment_index = int(row.get("fragment_index") or 0)
        payload = {
            "fragment_index": fragment_index,
            "proposed_document_type": str(row.get("proposed_document_type") or "") or None,
            "parsed_valid_until": row.get("parsed_valid_until"),
            "parsed_issued_at": row.get("parsed_issued_at"),
            "parsed_hours": row.get("parsed_hours"),
            "certificate_number": str(row.get("certificate_number") or "") or None,
            "organization": str(row.get("organization") or "") or None,
            "title": str(row.get("title") or "") or None,
            "specialty": str(row.get("specialty") or "") or None,
            "parse_method": str(row.get("parse_method") or "") or "regex_v1",
            "confidence_score": row.get("confidence_score"),
        }
        index[(row_id, source_field, norm_source_text(raw_text))] = payload
        index[(row_id, source_field, fragment_index)] = payload
    return index


def _lookup_candidate_enrichment(
    index: dict[tuple[Any, ...], dict[str, Any]],
    *,
    row_id: int,
    source_field: str,
    source_text: str,
    fragment_index: int,
) -> dict[str, Any]:
    by_text = index.get((row_id, source_field, norm_source_text(source_text)))
    if by_text:
        return by_text
    return index.get((row_id, source_field, fragment_index), {})


def _build_staging_rows_for_profile(
    *,
    batch_id: int,
    row_id: int,
    employee_id: Optional[int],
    profile: dict[str, Any],
    candidate_index: dict[tuple[Any, ...], dict[str, Any]],
    document_type_ids: dict[str, int],
    open_employee_keys: set[tuple[int, str]],
) -> list[dict[str, Any]]:
    builders: list[tuple[str, list[dict[str, Any]]]] = [
        (RECORD_KIND_TRAINING, profile.get("training_records") or []),
        (RECORD_KIND_CERTIFICATE, profile.get("certificate_records") or []),
        (RECORD_KIND_CATEGORY, profile.get("category_records") or []),
        (RECORD_KIND_EDUCATION, profile.get("education_records") or []),
    ]

    staging_rows: list[dict[str, Any]] = []
    for record_kind, records in builders:
        for fragment_index, record in enumerate(records):
            source_field = str(record.get("source_field") or "")
            source_text = str(record.get("source_text") or "")
            enrichment = _lookup_candidate_enrichment(
                candidate_index,
                row_id=row_id,
                source_field=source_field,
                source_text=source_text,
                fragment_index=fragment_index,
            )
            effective_fragment_index = int(
                enrichment.get("fragment_index") if enrichment.get("fragment_index") is not None else fragment_index
            )

            if record_kind == RECORD_KIND_TRAINING:
                title = str(record.get("title") or enrichment.get("title") or source_text or "")
                provider = str(record.get("organization") or enrichment.get("organization") or "")
                issue_date = _coerce_date(record.get("completed_at")) or _coerce_date(
                    enrichment.get("parsed_issued_at")
                )
                start_date = _coerce_date(record.get("started_at"))
                end_date = None
                expiry_date = _coerce_date(enrichment.get("parsed_valid_until"))
                hours = _coerce_hours(record.get("hours"))
                if hours is None:
                    hours = _coerce_hours(enrichment.get("parsed_hours"))
                document_number = ""
                specialty_text = ""
            elif record_kind == RECORD_KIND_CERTIFICATE:
                title = str(
                    record.get("topic")
                    or record.get("kind")
                    or enrichment.get("title")
                    or source_text
                    or ""
                )
                provider = str(record.get("kind") or enrichment.get("organization") or "")
                issue_date = _coerce_date(record.get("issued_at")) or _coerce_date(
                    enrichment.get("parsed_issued_at")
                )
                start_date = None
                end_date = None
                expiry_date = _coerce_date(record.get("valid_until")) or _coerce_date(
                    enrichment.get("parsed_valid_until")
                )
                hours = _coerce_hours(record.get("hours"))
                if hours is None:
                    hours = _coerce_hours(enrichment.get("parsed_hours"))
                document_number = str(record.get("certificate_number") or enrichment.get("certificate_number") or "")
                specialty_text = str(record.get("specialty") or enrichment.get("specialty") or "")
            elif record_kind == RECORD_KIND_CATEGORY:
                title = str(record.get("category") or enrichment.get("title") or source_text or "")
                provider = ""
                issue_date, expiry_date = _resolve_category_issue_expiry_dates(
                    record,
                    enrichment,
                    source_text,
                )
                start_date = None
                end_date = None
                hours = _coerce_hours(enrichment.get("parsed_hours"))
                document_number = str(enrichment.get("certificate_number") or "")
                specialty_text = str(record.get("specialty") or enrichment.get("specialty") or "")
            else:
                title = str(record.get("institution") or enrichment.get("title") or source_text or "")
                provider = str(record.get("institution") or enrichment.get("organization") or "")
                issue_date = _coerce_date(record.get("completed_at")) or _coerce_date(
                    enrichment.get("parsed_issued_at")
                )
                start_date = None
                end_date = None
                expiry_date = None
                hours = _coerce_hours(enrichment.get("parsed_hours"))
                document_number = ""
                specialty_text = str(record.get("specialty") or enrichment.get("specialty") or "")

            if not source_field:
                source_field = {
                    RECORD_KIND_TRAINING: "education_training_raw",
                    RECORD_KIND_CERTIFICATE: "certification_raw",
                    RECORD_KIND_CATEGORY: "certification_raw",
                    RECORD_KIND_EDUCATION: "education_raw",
                }[record_kind]

            proposed_code = enrichment.get("proposed_document_type")
            document_type_code = _resolve_document_type_code(
                record_kind,
                proposed_code=str(proposed_code) if proposed_code else None,
            )
            document_type_id = (
                document_type_ids.get(document_type_code)
                if document_type_code
                else None
            )

            parse_method = str(record.get("parse_method") or enrichment.get("parse_method") or "regex_v1")
            confidence = _coerce_confidence(record.get("confidence"))
            if confidence is None:
                confidence = _coerce_confidence(enrichment.get("confidence_score"))

            source_record_key = compute_source_record_key(
                row_id=row_id,
                employee_id=employee_id,
                record_kind=record_kind,
                title=title,
                issue_date=issue_date,
                end_date=end_date,
                hours=hours,
                document_number=document_number,
                source_field=source_field,
                fragment_index=effective_fragment_index,
            )

            if employee_id is not None:
                open_key = (employee_id, source_record_key)
                if open_key in open_employee_keys:
                    continue
                open_employee_keys.add(open_key)

            staging_rows.append(
                {
                    "batch_id": batch_id,
                    "row_id": row_id,
                    "employee_id": employee_id,
                    "fragment_index": effective_fragment_index,
                    "source_field": source_field,
                    "source_text": source_text or title or provider,
                    "source_record_key": source_record_key,
                    "record_kind": record_kind,
                    "document_type_id": document_type_id,
                    "document_type_code": document_type_code or proposed_code,
                    "title": title or None,
                    "provider": provider or None,
                    "hours": hours,
                    "start_date": start_date,
                    "end_date": end_date,
                    "issue_date": issue_date,
                    "expiry_date": expiry_date,
                    "document_number": document_number or None,
                    "specialty_text": specialty_text or None,
                    "file_url": str(record.get("link") or "") or None,
                    "parse_method": parse_method,
                    "confidence": confidence,
                    "review_status": REVIEW_STATUS_PENDING,
                }
            )
    return staging_rows


def _insert_staging_row(conn: Connection, row: dict[str, Any]) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.hr_import_normalized_records (
                batch_id,
                row_id,
                employee_id,
                fragment_index,
                source_field,
                source_text,
                source_record_key,
                record_kind,
                document_type_id,
                document_type_code,
                title,
                provider,
                hours,
                start_date,
                end_date,
                issue_date,
                expiry_date,
                document_number,
                specialty_text,
                file_url,
                parse_method,
                confidence,
                review_status
            )
            VALUES (
                :batch_id,
                :row_id,
                :employee_id,
                :fragment_index,
                :source_field,
                :source_text,
                :source_record_key,
                :record_kind,
                :document_type_id,
                :document_type_code,
                :title,
                :provider,
                :hours,
                :start_date,
                :end_date,
                :issue_date,
                :expiry_date,
                :document_number,
                :specialty_text,
                :file_url,
                :parse_method,
                :confidence,
                :review_status
            )
            ON CONFLICT (row_id, source_record_key) DO UPDATE SET
                employee_id = EXCLUDED.employee_id,
                fragment_index = EXCLUDED.fragment_index,
                source_field = EXCLUDED.source_field,
                source_text = EXCLUDED.source_text,
                record_kind = EXCLUDED.record_kind,
                document_type_id = EXCLUDED.document_type_id,
                document_type_code = EXCLUDED.document_type_code,
                title = EXCLUDED.title,
                provider = EXCLUDED.provider,
                hours = EXCLUDED.hours,
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date,
                issue_date = EXCLUDED.issue_date,
                expiry_date = EXCLUDED.expiry_date,
                document_number = EXCLUDED.document_number,
                specialty_text = EXCLUDED.specialty_text,
                file_url = EXCLUDED.file_url,
                parse_method = EXCLUDED.parse_method,
                confidence = EXCLUDED.confidence,
                updated_at = NOW()
            WHERE public.hr_import_normalized_records.promoted_document_id IS NULL
              AND public.hr_import_normalized_records.review_status IN ('pending', 'rejected', 'superseded')
            """
        ),
        row,
    )


def _delete_rebuildable_records(conn: Connection, batch_id: int) -> int:
    result = conn.execute(
        text(
            """
            DELETE FROM public.hr_import_normalized_records
            WHERE batch_id = :batch_id
              AND promoted_document_id IS NULL
              AND review_status IN ('pending', 'rejected', 'superseded')
            """
        ),
        {"batch_id": batch_id},
    )
    return int(result.rowcount or 0)


def _populate_batch(conn: Connection, batch_id: int) -> dict[str, int]:
    candidate_index = _load_candidate_enrichment(conn, batch_id)
    document_type_ids = _load_document_type_ids(conn)
    counts = {
        RECORD_KIND_TRAINING: 0,
        RECORD_KIND_CERTIFICATE: 0,
        RECORD_KIND_CATEGORY: 0,
        RECORD_KIND_EDUCATION: 0,
    }
    open_employee_keys: set[tuple[int, str]] = set()

    for row in _load_rows_for_population(conn, batch_id):
        row_id = row["row_id"]
        payload = row["payload"]
        employee_id = row["employee_id"]
        meta = _load_effective_profile_meta(
            conn,
            batch_id,
            row_id,
            payload=payload,
            row_employee_id=employee_id,
        )
        profile = _resolve_merged_profile(payload, meta)
        staging_rows = _build_staging_rows_for_profile(
            batch_id=batch_id,
            row_id=row_id,
            employee_id=employee_id,
            profile=profile,
            candidate_index=candidate_index,
            document_type_ids=document_type_ids,
            open_employee_keys=open_employee_keys,
        )
        for staging_row in staging_rows:
            _insert_staging_row(conn, staging_row)
            counts[staging_row["record_kind"]] += 1

    return counts


def populate_normalized_records(conn: Connection, batch_id: int) -> dict[str, Any]:
    """Rebuild staging normalized records for a batch. Never writes employee_documents."""
    if not normalized_records_available(conn):
        return {
            "batch_id": batch_id,
            "training_records": 0,
            "certificate_records": 0,
            "category_records": 0,
            "education_records": 0,
            "total_records": 0,
            "deleted_records": 0,
            "skipped": True,
        }

    _ensure_batch_exists(conn, batch_id)
    deleted = _delete_rebuildable_records(conn, batch_id)
    counts = _populate_batch(conn, batch_id)
    total = sum(counts.values())
    return {
        "batch_id": batch_id,
        "training_records": counts[RECORD_KIND_TRAINING],
        "certificate_records": counts[RECORD_KIND_CERTIFICATE],
        "category_records": counts[RECORD_KIND_CATEGORY],
        "education_records": counts[RECORD_KIND_EDUCATION],
        "total_records": total,
        "deleted_records": deleted,
        "skipped": False,
    }


def normalized_records_summary(conn: Connection, batch_id: int) -> dict[str, Any]:
    """Counts by record_kind and review_status for a batch."""
    _ensure_batch_exists(conn, batch_id)
    if not normalized_records_available(conn):
        return {
            "batch_id": batch_id,
            "total_records": 0,
            "by_kind": {},
            "by_status": {},
            "skipped": True,
        }

    rows = conn.execute(
        text(
            """
            SELECT record_kind, review_status, COUNT(*) AS cnt
            FROM public.hr_import_normalized_records
            WHERE batch_id = :batch_id
            GROUP BY record_kind, review_status
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()

    by_kind: dict[str, int] = {}
    by_status: dict[str, int] = {}
    total = 0
    for row in rows:
        kind = str(row["record_kind"])
        status = str(row["review_status"])
        count = int(row["cnt"])
        total += count
        by_kind[kind] = by_kind.get(kind, 0) + count
        by_status[status] = by_status.get(status, 0) + count

    return {
        "batch_id": batch_id,
        "total_records": total,
        "by_kind": by_kind,
        "by_status": by_status,
        "skipped": False,
    }


def list_normalized_records(
    conn: Connection,
    batch_id: int,
    *,
    record_kind: Optional[str] = None,
    review_status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    _ensure_batch_exists(conn, batch_id)
    if not normalized_records_available(conn):
        return {
            "batch_id": batch_id,
            "total": 0,
            "limit": limit,
            "offset": offset,
            "items": [],
            "skipped": True,
        }

    clauses = ["batch_id = :batch_id"]
    params: dict[str, Any] = {"batch_id": batch_id, "limit": limit, "offset": offset}
    if record_kind:
        clauses.append("record_kind = :record_kind")
        params["record_kind"] = record_kind
    if review_status:
        clauses.append("review_status = :review_status")
        params["review_status"] = review_status

    where_sql = " AND ".join(clauses)
    total = int(
        conn.execute(
            text(f"SELECT COUNT(*) FROM public.hr_import_normalized_records WHERE {where_sql}"),
            params,
        ).scalar_one()
    )
    db_rows = conn.execute(
        text(
            f"""
            SELECT *
            FROM public.hr_import_normalized_records
            WHERE {where_sql}
            ORDER BY row_id, record_kind, fragment_index, normalized_record_id
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    items: list[dict[str, Any]] = []
    for db_row in db_rows:
        item = dict(db_row)
        for date_field in ("start_date", "end_date", "issue_date", "expiry_date"):
            value = item.get(date_field)
            if value is not None and hasattr(value, "isoformat"):
                item[date_field] = value.isoformat()
        confidence = item.get("confidence")
        if isinstance(confidence, Decimal):
            item["confidence"] = float(confidence)
        items.append(item)

    return {
        "batch_id": batch_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
        "skipped": False,
    }


class NormalizedRecordNotFoundError(Exception):
    def __init__(self, record_id: int) -> None:
        self.record_id = record_id
        super().__init__(f"Normalized record {record_id} not found")


class InvalidReviewTransitionError(Exception):
    def __init__(self, current_status: str, target_status: str) -> None:
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Cannot change review_status from {current_status} to {target_status}"
        )


def _isoformat_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _serialize_normalized_record(row: dict[str, Any]) -> dict[str, Any]:
    confidence = row.get("confidence")
    full_name = str(row.get("full_name") or "").strip()
    iin_raw = str(row.get("row_iin") or row.get("iin") or "").strip()
    return {
        "record_id": int(row["normalized_record_id"]),
        "normalized_record_id": int(row["normalized_record_id"]),
        "batch_id": int(row["batch_id"]),
        "row_id": int(row["row_id"]),
        "employee_id": int(row["employee_id"]) if row.get("employee_id") is not None else None,
        "full_name": full_name,
        "iin_masked": mask_iin(iin_raw) if iin_raw else "",
        "fragment_index": int(row.get("fragment_index") or 0),
        "source_field": row.get("source_field") or "",
        "source_text": row.get("source_text") or "",
        "source_record_key": row.get("source_record_key") or "",
        "record_kind": row.get("record_kind") or "",
        "document_type_id": int(row["document_type_id"]) if row.get("document_type_id") is not None else None,
        "document_type_code": row.get("document_type_code"),
        "title": row.get("title"),
        "provider": row.get("provider"),
        "hours": int(row["hours"]) if row.get("hours") is not None else None,
        "start_date": _isoformat_or_none(row.get("start_date")),
        "end_date": _isoformat_or_none(row.get("end_date")),
        "issue_date": _isoformat_or_none(row.get("issue_date")),
        "expiry_date": _isoformat_or_none(row.get("expiry_date")),
        "document_number": row.get("document_number"),
        "specialty_text": row.get("specialty_text"),
        "medical_specialty_id": int(row["medical_specialty_id"])
        if row.get("medical_specialty_id") is not None
        else None,
        "file_url": row.get("file_url"),
        "parse_method": row.get("parse_method") or "",
        "confidence": float(confidence) if isinstance(confidence, Decimal) else confidence,
        "review_status": row.get("review_status") or REVIEW_STATUS_PENDING,
        "reviewed_at": _isoformat_or_none(row.get("reviewed_at")),
        "reviewed_by": int(row["reviewed_by"]) if row.get("reviewed_by") is not None else None,
        "review_notes": row.get("review_notes"),
        "promoted_document_id": int(row["promoted_document_id"])
        if row.get("promoted_document_id") is not None
        else None,
        "promoted_at": _isoformat_or_none(row.get("promoted_at")),
        "promoted_by": int(row["promoted_by"]) if row.get("promoted_by") is not None else None,
        "created_at": _isoformat_or_none(row.get("created_at")),
        "updated_at": _isoformat_or_none(row.get("updated_at")),
    }


def _empty_review_summary() -> dict[str, Any]:
    return {
        "total": 0,
        "pending": 0,
        "approved": 0,
        "rejected": 0,
        "promoted": 0,
        "superseded": 0,
        "by_kind": {
            RECORD_KIND_TRAINING: 0,
            RECORD_KIND_CERTIFICATE: 0,
            RECORD_KIND_CATEGORY: 0,
            RECORD_KIND_EDUCATION: 0,
        },
        "skipped": True,
    }


def review_normalized_records_summary(
    conn: Connection,
    *,
    batch_id: Optional[int] = None,
) -> dict[str, Any]:
    """ADR-039 Phase 3D — aggregate review counts for staging normalized records."""
    if batch_id is not None:
        _ensure_batch_exists(conn, batch_id)
    if not normalized_records_available(conn):
        return _empty_review_summary()

    clauses: list[str] = []
    params: dict[str, Any] = {}
    if batch_id is not None:
        clauses.append("batch_id = :batch_id")
        params["batch_id"] = batch_id
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    status_rows = conn.execute(
        text(
            f"""
            SELECT review_status, COUNT(*) AS cnt
            FROM public.hr_import_normalized_records
            {where_sql}
            GROUP BY review_status
            """
        ),
        params,
    ).mappings().all()
    kind_rows = conn.execute(
        text(
            f"""
            SELECT record_kind, COUNT(*) AS cnt
            FROM public.hr_import_normalized_records
            {where_sql}
            GROUP BY record_kind
            """
        ),
        params,
    ).mappings().all()

    by_status = {str(row["review_status"]): int(row["cnt"]) for row in status_rows}
    by_kind_raw = {str(row["record_kind"]): int(row["cnt"]) for row in kind_rows}
    by_kind = {
        RECORD_KIND_TRAINING: by_kind_raw.get(RECORD_KIND_TRAINING, 0),
        RECORD_KIND_CERTIFICATE: by_kind_raw.get(RECORD_KIND_CERTIFICATE, 0),
        RECORD_KIND_CATEGORY: by_kind_raw.get(RECORD_KIND_CATEGORY, 0),
        RECORD_KIND_EDUCATION: by_kind_raw.get(RECORD_KIND_EDUCATION, 0),
    }
    total = sum(by_status.values())

    return {
        "total": total,
        "pending": by_status.get(REVIEW_STATUS_PENDING, 0),
        "approved": by_status.get(REVIEW_STATUS_APPROVED, 0),
        "rejected": by_status.get(REVIEW_STATUS_REJECTED, 0),
        "promoted": by_status.get(REVIEW_STATUS_PROMOTED, 0),
        "superseded": by_status.get(REVIEW_STATUS_SUPERSEDED, 0),
        "by_kind": by_kind,
        "skipped": False,
    }


def _normalized_record_list_join_sql() -> str:
    return """
        FROM public.hr_import_normalized_records nr
        JOIN public.hr_import_rows r ON r.row_id = nr.row_id
    """


def _normalized_record_identity_sql() -> str:
    return """
        trim(COALESCE(r.normalized_payload->>'full_name', '')) AS full_name,
        trim(COALESCE(r.normalized_payload->>'iin', '')) AS row_iin
    """


def _fetch_normalized_record_row(conn: Connection, record_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            f"""
            SELECT nr.*, {_normalized_record_identity_sql()}
            {_normalized_record_list_join_sql()}
            WHERE nr.normalized_record_id = :record_id
            """
        ),
        {"record_id": record_id},
    ).mappings().first()
    return dict(row) if row is not None else None


def list_review_normalized_records(
    conn: Connection,
    *,
    batch_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    review_status: Optional[str] = None,
    record_kind: Optional[str] = None,
    q_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """ADR-039 Phase 3D — list staging normalized records with review filters."""
    if batch_id is not None:
        _ensure_batch_exists(conn, batch_id)
    if review_status is not None and review_status not in REVIEW_STATUSES:
        raise ValueError(f"invalid review_status: {review_status}")
    if record_kind is not None and record_kind not in RECORD_KINDS:
        raise ValueError(f"invalid record_kind: {record_kind}")

    if not normalized_records_available(conn):
        return {
            "total": 0,
            "limit": limit,
            "offset": offset,
            "items": [],
            "skipped": True,
        }

    clauses: list[str] = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if batch_id is not None:
        clauses.append("nr.batch_id = :batch_id")
        params["batch_id"] = batch_id
    if employee_id is not None:
        clauses.append("nr.employee_id = :employee_id")
        params["employee_id"] = employee_id
    if review_status is not None:
        clauses.append("nr.review_status = :review_status")
        params["review_status"] = review_status
    if record_kind is not None:
        clauses.append("nr.record_kind = :record_kind")
        params["record_kind"] = record_kind
    if q_name:
        clauses.append(
            "lower(trim(COALESCE(r.normalized_payload->>'full_name', ''))) LIKE :q_name_pattern"
        )
        params["q_name_pattern"] = f"%{q_name.strip().lower()}%"

    where_sql = " AND ".join(clauses) if clauses else "TRUE"
    join_sql = _normalized_record_list_join_sql()
    total = int(
        conn.execute(
            text(f"SELECT COUNT(*) {join_sql} WHERE {where_sql}"),
            params,
        ).scalar_one()
    )
    db_rows = conn.execute(
        text(
            f"""
            SELECT nr.*, {_normalized_record_identity_sql()}
            {join_sql}
            WHERE {where_sql}
            ORDER BY nr.created_at DESC, nr.normalized_record_id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_serialize_normalized_record(dict(row)) for row in db_rows],
        "skipped": False,
    }


def update_normalized_record_review(
    conn: Connection,
    record_id: int,
    *,
    review_status: str,
    reviewed_by: int,
    review_notes: Optional[str] = None,
) -> dict[str, Any]:
    """ADR-039 Phase 3D — transition review_status without writing employee_documents."""
    if review_status not in REVIEW_STATUSES:
        raise ValueError(f"invalid review_status: {review_status}")

    if not normalized_records_available(conn):
        raise NormalizedRecordNotFoundError(record_id)

    row = _fetch_normalized_record_row(conn, record_id)
    if row is None:
        raise NormalizedRecordNotFoundError(record_id)

    current_status = str(row["review_status"])
    if review_status == current_status:
        return _serialize_normalized_record(row)

    allowed = ALLOWED_REVIEW_TRANSITIONS.get(current_status, frozenset())
    if review_status not in allowed:
        raise InvalidReviewTransitionError(current_status, review_status)

    if review_status in {REVIEW_STATUS_APPROVED, REVIEW_STATUS_REJECTED}:
        conn.execute(
            text(
                """
                UPDATE public.hr_import_normalized_records
                SET
                    review_status = :review_status,
                    reviewed_at = NOW(),
                    reviewed_by = :reviewed_by,
                    review_notes = :review_notes,
                    updated_at = NOW()
                WHERE normalized_record_id = :record_id
                """
            ),
            {
                "record_id": record_id,
                "review_status": review_status,
                "reviewed_by": reviewed_by,
                "review_notes": review_notes,
            },
        )
    else:
        conn.execute(
            text(
                """
                UPDATE public.hr_import_normalized_records
                SET
                    review_status = :review_status,
                    reviewed_at = NULL,
                    reviewed_by = NULL,
                    review_notes = NULL,
                    updated_at = NOW()
                WHERE normalized_record_id = :record_id
                """
            ),
            {
                "record_id": record_id,
                "review_status": review_status,
            },
        )

    updated = _fetch_normalized_record_row(conn, record_id)
    if updated is None:
        raise NormalizedRecordNotFoundError(record_id)
    return _serialize_normalized_record(updated)
