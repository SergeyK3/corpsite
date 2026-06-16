"""Build and query hr_import_document_candidates from staging rows (Phase 2C)."""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.hr_import_analytics_service import BatchNotFoundError, _ensure_batch_exists
from app.services.hr_import_document_parser import (
    ParsedDocumentFragment,
    parse_certification_raw,
    parse_education_raw,
    parse_education_training_raw,
)
from scripts.import_hr_control_list import mask_iin

DOCUMENT_KIND_TRAINING = "training"
DOCUMENT_KIND_CERTIFICATION = "certification"
DOCUMENT_KIND_EDUCATION = "education"


def _lookup_identity_id(conn: Connection, iin: str) -> Optional[int]:
    if not iin:
        return None
    row = conn.execute(
        text(
            """
            SELECT identity_id
            FROM public.employee_identities
            WHERE identity_type = 'IIN'
              AND identity_value = :iin
              AND valid_to IS NULL
            ORDER BY is_primary DESC, identity_id
            LIMIT 1
            """
        ),
        {"iin": iin},
    ).first()
    return int(row[0]) if row else None


def _load_rows_for_candidates(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    _ensure_batch_exists(conn, batch_id)
    db_rows = conn.execute(
        text(
            """
            SELECT
                row_id,
                batch_id,
                source_sheet,
                source_row_number,
                employee_id,
                normalized_payload
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
        iin = str(payload.get("iin", "") or "").strip()
        items.append(
            {
                "row_id": int(db_row["row_id"]),
                "batch_id": int(db_row["batch_id"]),
                "source_sheet": str(db_row["source_sheet"] or ""),
                "source_row_number": int(db_row["source_row_number"]),
                "employee_id": int(db_row["employee_id"]) if db_row["employee_id"] else None,
                "full_name": str(payload.get("full_name", "") or "").strip(),
                "iin": iin,
                "department": str(payload.get("department", "") or "").strip(),
                "position": str(payload.get("position_raw", "") or "").strip(),
                "training_raw": str(payload.get("training_raw", "") or "").strip(),
                "education_training_raw": str(
                    payload.get("education_training_raw", "") or payload.get("training_raw", "") or ""
                ).strip(),
                "certification_raw": str(payload.get("certification_raw", "") or "").strip(),
                "education_raw": str(payload.get("education_raw", "") or "").strip(),
                "diploma_specialty_raw": str(payload.get("diploma_specialty_raw", "") or "").strip(),
                "is_employee_roster": bool(metadata.get("is_employee_roster", False)),
            }
        )
    return items


def _has_source_field_column(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'hr_import_document_candidates'
              AND column_name = 'source_field'
            """
        )
    ).first()
    return row is not None


def _insert_candidate(
    conn: Connection,
    *,
    row: dict[str, Any],
    fragment: ParsedDocumentFragment,
    employee_identity_id: Optional[int],
) -> None:
    params = {
        "batch_id": row["batch_id"],
        "row_id": row["row_id"],
        "employee_id": row["employee_id"],
        "employee_identity_id": employee_identity_id,
        "full_name": row["full_name"] or None,
        "iin": row["iin"] or None,
        "department": row["department"] or None,
        "position": row["position"] or None,
        "document_kind": fragment.document_kind,
        "proposed_document_type": fragment.proposed_document_type,
        "title": fragment.title,
        "organization": fragment.organization,
        "parsed_hours": fragment.parsed_hours,
        "parsed_issued_at": fragment.parsed_issued_at,
        "parsed_valid_until": fragment.parsed_valid_until,
        "specialty": fragment.specialty,
        "category": fragment.category,
        "certificate_number": fragment.certificate_number,
        "raw_text": fragment.raw_text,
        "source_sheet": row["source_sheet"],
        "source_row": row["source_row_number"],
        "fragment_index": fragment.fragment_index,
        "parse_method": fragment.parse_method,
        "confidence_score": fragment.confidence_score,
        "source_field": fragment.source_field,
    }
    if _has_source_field_column(conn):
        sql = """
            INSERT INTO public.hr_import_document_candidates (
                batch_id, row_id, employee_id, employee_identity_id,
                full_name, iin, department, position,
                document_kind, proposed_document_type, title, organization,
                parsed_hours, parsed_issued_at, parsed_valid_until,
                specialty, category, certificate_number,
                raw_text, source_sheet, source_row,
                external_url, storage_type, storage_path,
                fragment_index, parse_method, confidence_score, review_status,
                source_field
            )
            VALUES (
                :batch_id, :row_id, :employee_id, :employee_identity_id,
                :full_name, :iin, :department, :position,
                :document_kind, :proposed_document_type, :title, :organization,
                :parsed_hours, :parsed_issued_at, :parsed_valid_until,
                :specialty, :category, :certificate_number,
                :raw_text, :source_sheet, :source_row,
                NULL, NULL, NULL,
                :fragment_index, :parse_method, :confidence_score, 'PENDING',
                :source_field
            )
        """
    else:
        sql = """
            INSERT INTO public.hr_import_document_candidates (
                batch_id, row_id, employee_id, employee_identity_id,
                full_name, iin, department, position,
                document_kind, proposed_document_type, title, organization,
                parsed_hours, parsed_issued_at, parsed_valid_until,
                specialty, category, certificate_number,
                raw_text, source_sheet, source_row,
                external_url, storage_type, storage_path,
                fragment_index, parse_method, confidence_score, review_status
            )
            VALUES (
                :batch_id, :row_id, :employee_id, :employee_identity_id,
                :full_name, :iin, :department, :position,
                :document_kind, :proposed_document_type, :title, :organization,
                :parsed_hours, :parsed_issued_at, :parsed_valid_until,
                :specialty, :category, :certificate_number,
                :raw_text, :source_sheet, :source_row,
                NULL, NULL, NULL,
                :fragment_index, :parse_method, :confidence_score, 'PENDING'
            )
        """
    conn.execute(text(sql), params)


def _phase_2c_schema_ready(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'hr_import_document_candidates'
              AND column_name = 'batch_id'
            """
        )
    ).first()
    return row is not None


def parse_and_persist_document_candidates(conn: Connection, batch_id: int) -> dict[str, int]:
    """Idempotently rebuild document candidates for a batch. Never writes employee_documents."""
    if not _phase_2c_schema_ready(conn):
        return {
            "batch_id": batch_id,
            "training_candidates": 0,
            "certification_candidates": 0,
            "education_candidates": 0,
            "total_candidates": 0,
            "skipped": True,
        }
    _ensure_batch_exists(conn, batch_id)
    conn.execute(
        text(
            """
            DELETE FROM public.hr_import_document_candidates
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    )

    training_count = 0
    certification_count = 0
    education_count = 0
    for row in _load_rows_for_candidates(conn, batch_id):
        if not row.get("is_employee_roster", False):
            continue
        identity_id = _lookup_identity_id(conn, row["iin"])
        for fragment in parse_education_training_raw(row["education_training_raw"]):
            _insert_candidate(conn, row=row, fragment=fragment, employee_identity_id=identity_id)
            if fragment.document_kind == DOCUMENT_KIND_TRAINING:
                training_count += 1
            elif fragment.document_kind == DOCUMENT_KIND_EDUCATION:
                education_count += 1
        for fragment in parse_certification_raw(row["certification_raw"]):
            _insert_candidate(conn, row=row, fragment=fragment, employee_identity_id=identity_id)
            certification_count += 1
        for fragment in parse_education_raw(row["education_raw"], row["diploma_specialty_raw"]):
            _insert_candidate(conn, row=row, fragment=fragment, employee_identity_id=identity_id)
            education_count += 1

    return {
        "batch_id": batch_id,
        "training_candidates": training_count,
        "certification_candidates": certification_count,
        "education_candidates": education_count,
        "total_candidates": training_count + certification_count + education_count,
    }


def _serialize_candidate(row: dict[str, Any]) -> dict[str, Any]:
    iin = str(row.get("iin") or "")
    hours = row.get("parsed_hours")
    confidence = row.get("confidence_score")
    return {
        "candidate_id": int(row["candidate_id"]),
        "batch_id": int(row["batch_id"]),
        "row_id": int(row["row_id"]),
        "employee_id": int(row["employee_id"]) if row.get("employee_id") else None,
        "employee_identity_id": int(row["employee_identity_id"])
        if row.get("employee_identity_id")
        else None,
        "full_name": row.get("full_name") or "",
        "iin_masked": mask_iin(iin) if iin else "",
        "department": row.get("department") or "",
        "position": row.get("position") or "",
        "document_type": row.get("proposed_document_type") or "",
        "document_kind": row.get("document_kind") or "",
        "title": row.get("title") or "",
        "organization": row.get("organization") or "",
        "issued_at": row["parsed_issued_at"].isoformat() if row.get("parsed_issued_at") else None,
        "valid_until": row["parsed_valid_until"].isoformat() if row.get("parsed_valid_until") else None,
        "hours": float(hours) if hours is not None else None,
        "specialty": row.get("specialty") or "",
        "category": row.get("category") or "",
        "certificate_number": row.get("certificate_number") or "",
        "raw_text": row.get("raw_text") or "",
        "source_sheet": row.get("source_sheet") or "",
        "source_row": int(row["source_row"]) if row.get("source_row") is not None else None,
        "external_url": row.get("external_url") or "",
        "storage_type": row.get("storage_type") or "",
        "storage_path": row.get("storage_path") or "",
        "status": row.get("review_status") or "PENDING",
        "fragment_index": int(row.get("fragment_index") or 0),
        "confidence_score": float(confidence) if confidence is not None else None,
        "parse_method": row.get("parse_method") or "",
        "source_field": row.get("source_field") or "",
    }


def document_candidates_summary(conn: Connection, batch_id: int) -> dict[str, Any]:
    _ensure_batch_exists(conn, batch_id)
    rows = conn.execute(
        text(
            """
            SELECT document_kind, review_status, COUNT(*) AS cnt
            FROM public.hr_import_document_candidates
            WHERE batch_id = :batch_id
            GROUP BY document_kind, review_status
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()

    by_kind = {
        DOCUMENT_KIND_TRAINING: 0,
        DOCUMENT_KIND_CERTIFICATION: 0,
        DOCUMENT_KIND_EDUCATION: 0,
    }
    by_status: dict[str, int] = {}
    total = 0
    for row in rows:
        kind = str(row["document_kind"])
        status = str(row["review_status"])
        count = int(row["cnt"])
        total += count
        by_kind[kind] = by_kind.get(kind, 0) + count
        by_status[status] = by_status.get(status, 0) + count

    return {
        "batch_id": batch_id,
        "total_candidates": total,
        "by_kind": by_kind,
        "by_status": by_status,
    }


def list_document_candidates(
    conn: Connection,
    batch_id: int,
    *,
    document_kind: Optional[str] = None,
    status: Optional[str] = None,
    department: Optional[str] = None,
    q_name: Optional[str] = None,
    has_hours: Optional[bool] = None,
    has_valid_until: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    _ensure_batch_exists(conn, batch_id)

    clauses = ["batch_id = :batch_id"]
    params: dict[str, Any] = {"batch_id": batch_id, "limit": limit, "offset": offset}

    if document_kind:
        clauses.append("document_kind = :document_kind")
        params["document_kind"] = document_kind
    if status:
        clauses.append("review_status = :status")
        params["status"] = status
    if department:
        clauses.append("department = :department")
        params["department"] = department
    if q_name:
        clauses.append("LOWER(full_name) LIKE :q_name")
        params["q_name"] = f"%{q_name.strip().lower()}%"
    if has_hours is True:
        clauses.append("parsed_hours IS NOT NULL")
    elif has_hours is False:
        clauses.append("parsed_hours IS NULL")
    if has_valid_until is True:
        clauses.append("parsed_valid_until IS NOT NULL")
    elif has_valid_until is False:
        clauses.append("parsed_valid_until IS NULL")

    where_sql = " AND ".join(clauses)
    total = int(
        conn.execute(
            text(f"SELECT COUNT(*) FROM public.hr_import_document_candidates WHERE {where_sql}"),
            params,
        ).scalar_one()
    )

    db_rows = conn.execute(
        text(
            f"""
            SELECT *
            FROM public.hr_import_document_candidates
            WHERE {where_sql}
            ORDER BY full_name NULLS LAST, row_id, fragment_index, candidate_id
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    return {
        "batch_id": batch_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_serialize_candidate(dict(r)) for r in db_rows],
    }


def employee_training_history(
    conn: Connection,
    batch_id: int,
    *,
    row_id: Optional[int] = None,
    q_name: Optional[str] = None,
) -> dict[str, Any]:
    _ensure_batch_exists(conn, batch_id)
    if row_id is None and not q_name:
        raise ValueError("row_id or q_name required")

    if row_id is not None:
        anchor = conn.execute(
            text(
                """
                SELECT row_id, full_name, iin, department, position, employee_id
                FROM public.hr_import_document_candidates
                WHERE batch_id = :batch_id AND row_id = :row_id
                LIMIT 1
                """
            ),
            {"batch_id": batch_id, "row_id": row_id},
        ).mappings().first()
        if not anchor:
            raise BatchNotFoundError(f"row_id={row_id} not found in batch {batch_id}")
        match_clause = "row_id = :match_row_id"
        match_params: dict[str, Any] = {"batch_id": batch_id, "match_row_id": row_id}
    else:
        anchor = conn.execute(
            text(
                """
                SELECT row_id, full_name, iin, department, position, employee_id
                FROM public.hr_import_document_candidates
                WHERE batch_id = :batch_id
                  AND LOWER(full_name) = :q_name
                ORDER BY row_id
                LIMIT 1
                """
            ),
            {"batch_id": batch_id, "q_name": q_name.strip().lower()},
        ).mappings().first()
        if not anchor:
            raise BatchNotFoundError(f"employee '{q_name}' not found in batch {batch_id}")
        iin = str(anchor.get("iin") or "")
        if iin:
            match_clause = "iin = :match_iin"
            match_params = {"batch_id": batch_id, "match_iin": iin}
        else:
            match_clause = "row_id = :match_row_id"
            match_params = {"batch_id": batch_id, "match_row_id": int(anchor["row_id"])}

    history_rows = conn.execute(
        text(
            f"""
            SELECT *
            FROM public.hr_import_document_candidates
            WHERE batch_id = :batch_id AND {match_clause}
            ORDER BY document_kind, parsed_issued_at NULLS LAST, fragment_index, candidate_id
            """
        ),
        match_params,
    ).mappings().all()

    iin = str(anchor.get("iin") or "")
    return {
        "batch_id": batch_id,
        "employee": {
            "row_id": int(anchor["row_id"]),
            "employee_id": int(anchor["employee_id"]) if anchor.get("employee_id") else None,
            "full_name": anchor.get("full_name") or "",
            "iin_masked": mask_iin(iin) if iin else "",
            "department": anchor.get("department") or "",
            "position": anchor.get("position") or "",
        },
        "items": [_serialize_candidate(dict(r)) for r in history_rows],
    }
