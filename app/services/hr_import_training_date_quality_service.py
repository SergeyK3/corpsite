"""ADR-059 — training/education date quality checks for import review."""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.hr_import_analytics_service import BatchNotFoundError, _ensure_batch_exists
from app.services.hr_import_document_parser import EDUCATION_SHARED_CONTEXT_REMARK
from app.services.hr_import_normalized_record_service import (
    RECORD_KIND_EDUCATION,
    RECORD_KIND_TRAINING,
    merge_review_override,
    normalized_records_available,
)

TRAINING_DATE_QUALITY_REMARK = "Требуется уточнить даты обучения"

_YEAR_ONLY_ISO_RE = re.compile(r"^\d{4}-01-01$")
_YEAR_TEXT_RE = re.compile(r"\b(19|20)\d{2}\b")
_FULL_DATE_TEXT_RE = re.compile(
    r"\b(\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{4}-\d{2}-\d{2})\b"
)
_YEAR_ONLY_TEXT_RE = re.compile(r"^\s*(19|20)\d{2}\s*$")


def _iso_to_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text_val = str(value).strip()
    if not text_val:
        return None
    try:
        return date.fromisoformat(text_val[:10])
    except ValueError:
        return None


def is_year_only_iso_date(value: Any) -> bool:
    text_val = str(value or "").strip()
    if not text_val:
        return False
    if _YEAR_ONLY_ISO_RE.match(text_val[:10]):
        return True
    parsed = _iso_to_date(text_val)
    return parsed is not None and parsed.month == 1 and parsed.day == 1


def is_incomplete_date_text(value: Any) -> bool:
    text_val = str(value or "").strip()
    if not text_val:
        return False
    if _YEAR_ONLY_TEXT_RE.match(text_val):
        return True
    if _FULL_DATE_TEXT_RE.search(text_val):
        return False
    return bool(_YEAR_TEXT_RE.search(text_val))


def _education_shared_context_ambiguous(record: dict[str, Any]) -> bool:
    if "shared_context_ambiguous" in str(record.get("parse_method") or ""):
        return True
    if str(record.get("record_kind") or "") != RECORD_KIND_EDUCATION:
        return False
    specialty_text = str(record.get("specialty_text") or "").strip()
    source_text = str(record.get("source_text") or record.get("title") or "").strip()
    if not specialty_text or not source_text:
        return False
    specialty_token = specialty_text.split(";", 1)[0].strip().casefold()
    if not specialty_token:
        return False
    return specialty_token not in source_text.casefold()


def assess_normalized_record_date_quality(record: dict[str, Any]) -> list[str]:
    record_kind = str(record.get("record_kind") or "")
    if record_kind not in {RECORD_KIND_TRAINING, RECORD_KIND_EDUCATION}:
        return []

    remarks: list[str] = []
    date_fields = ("start_date", "end_date", "issue_date")
    incomplete = False
    has_any_date = False

    for field in date_fields:
        raw = record.get(field)
        if raw in (None, ""):
            continue
        has_any_date = True
        if is_year_only_iso_date(raw):
            incomplete = True
            break

    if not incomplete:
        if not has_any_date and record_kind == RECORD_KIND_EDUCATION:
            incomplete = True
        else:
            has_full_date = any(
                record.get(field) not in (None, "")
                and not is_year_only_iso_date(record.get(field))
                for field in date_fields
            )
            if not has_full_date:
                source_text = str(record.get("source_text") or record.get("title") or "").strip()
                if is_incomplete_date_text(source_text):
                    incomplete = True

    if incomplete:
        remarks.append(TRAINING_DATE_QUALITY_REMARK)

    if record_kind == RECORD_KIND_EDUCATION and _education_shared_context_ambiguous(record):
        if EDUCATION_SHARED_CONTEXT_REMARK not in remarks:
            remarks.append(EDUCATION_SHARED_CONTEXT_REMARK)
    return remarks


def assess_roster_training_raw_quality(*, training_raw: str, education_raw: str) -> list[str]:
    remarks: list[str] = []
    for raw in (training_raw, education_raw):
        text_val = str(raw or "").strip()
        if text_val and is_incomplete_date_text(text_val):
            remarks.append(TRAINING_DATE_QUALITY_REMARK)
            break
    return remarks


def _effective_roster_training_fields(row: dict[str, Any]) -> tuple[str, str]:
    payload = dict(row.get("normalized_payload") or {})
    if isinstance(payload, str):
        payload = json.loads(payload)
    metadata = dict(payload.get("metadata") or {})
    override = dict(metadata.get("import_review_override") or {})
    training_raw = str(
        override.get("training_raw")
        if override.get("training_raw") is not None
        else payload.get("training_raw")
        or ""
    )
    education_raw = str(
        override.get("education_raw")
        if override.get("education_raw") is not None
        else payload.get("education_raw")
        or ""
    )
    return training_raw, education_raw


def _sort_key_full_name(full_name: str | None) -> tuple[str, int]:
    normalized = (full_name or "").strip().casefold()
    return (normalized, 0 if normalized else 1)


def list_training_date_quality_report(
    conn: Connection,
    batch_id: int,
    *,
    limit: int = 500,
    offset: int = 0,
) -> dict[str, Any]:
    """Employees / records with incomplete training or education dates (non-blocking)."""
    _ensure_batch_exists(conn, batch_id)
    items: list[dict[str, Any]] = []
    seen_normalized_ids: set[int] = set()
    rows_with_normalized_hits: set[int] = set()

    if normalized_records_available(conn):
        rows = conn.execute(
            text(
                """
                SELECT
                    nr.*,
                    COALESCE(r.employee_id, nr.employee_id) AS employee_id,
                    COALESCE(r.normalized_payload->>'full_name', '') AS full_name,
                    COALESCE(r.normalized_payload->>'department', '') AS department,
                    COALESCE(r.normalized_payload->>'position_raw', '') AS position_raw
                FROM public.hr_import_normalized_records nr
                LEFT JOIN public.hr_import_rows r ON r.row_id = nr.row_id
                WHERE nr.batch_id = :batch_id
                  AND nr.record_kind IN ('training', 'education')
                ORDER BY COALESCE(r.normalized_payload->>'full_name', ''), nr.normalized_record_id
                """
            ),
            {"batch_id": batch_id},
        ).mappings().all()

        for row in rows:
            record = dict(row)
            normalized_record_id = int(record["normalized_record_id"])
            if normalized_record_id in seen_normalized_ids:
                continue
            effective = merge_review_override(record)
            remarks = assess_normalized_record_date_quality(effective)
            if not remarks:
                continue
            seen_normalized_ids.add(normalized_record_id)
            row_id = int(record["row_id"]) if record.get("row_id") is not None else None
            if row_id is not None:
                rows_with_normalized_hits.add(row_id)
            items.append(
                {
                    "employee_id": int(record["employee_id"])
                    if record.get("employee_id") is not None
                    else None,
                    "row_id": row_id,
                    "normalized_record_id": normalized_record_id,
                    "full_name": str(record.get("full_name") or "").strip() or None,
                    "department": str(record.get("department") or "").strip() or None,
                    "position_raw": str(record.get("position_raw") or "").strip() or None,
                    "record_kind": str(record.get("record_kind") or ""),
                    "record_title": str(effective.get("title") or record.get("title") or "").strip()
                    or None,
                    "source_text": str(effective.get("source_text") or "").strip() or None,
                    "start_date": _iso_to_date(effective.get("start_date")),
                    "end_date": _iso_to_date(effective.get("end_date")),
                    "issue_date": _iso_to_date(effective.get("issue_date")),
                    "remarks": remarks,
                }
            )

    roster_rows = conn.execute(
        text(
            """
            SELECT
                row_id,
                employee_id,
                normalized_payload,
                COALESCE(normalized_payload->>'full_name', '') AS full_name,
                COALESCE(normalized_payload->>'department', '') AS department,
                COALESCE(normalized_payload->>'position_raw', '') AS position_raw
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
            ORDER BY COALESCE(normalized_payload->>'full_name', ''), row_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()

    for row in roster_rows:
        row_id = int(row["row_id"])
        if row_id in rows_with_normalized_hits:
            continue
        training_raw, education_raw = _effective_roster_training_fields(dict(row))
        remarks = assess_roster_training_raw_quality(
            training_raw=training_raw,
            education_raw=education_raw,
        )
        if not remarks:
            continue
        items.append(
            {
                "employee_id": int(row["employee_id"]) if row.get("employee_id") is not None else None,
                "row_id": row_id,
                "normalized_record_id": None,
                "full_name": str(row.get("full_name") or "").strip() or None,
                "department": str(row.get("department") or "").strip() or None,
                "position_raw": str(row.get("position_raw") or "").strip() or None,
                "record_kind": "roster",
                "record_title": None,
                "source_text": training_raw or education_raw or None,
                "start_date": None,
                "end_date": None,
                "issue_date": None,
                "remarks": remarks,
            }
        )

    items.sort(
        key=lambda item: (
            _sort_key_full_name(item.get("full_name")),
            int(item.get("normalized_record_id") or 0),
            int(item.get("row_id") or 0),
        )
    )
    total = len(items)
    page = items[offset : offset + limit]

    def _serialize(item: dict[str, Any]) -> dict[str, Any]:
        serialized = dict(item)
        for field in ("start_date", "end_date", "issue_date"):
            value = serialized.get(field)
            serialized[field] = value.isoformat() if isinstance(value, date) else value
        return serialized

    return {
        "batch_id": batch_id,
        "total": total,
        "remark": TRAINING_DATE_QUALITY_REMARK,
        "items": [_serialize(item) for item in page],
    }
