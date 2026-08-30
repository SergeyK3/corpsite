"""Read-only queries for operational-order archive import staging."""
from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from sqlalchemy import text

from app.db.engine import engine
from app.operational_orders.errors import (
    OperationalOrderArchiveReviewConflictError,
    OperationalOrderArchiveRowNotFoundError,
    OperationalOrderValidationError,
)

REVIEW_OUTCOMES = frozenset(
    {
        "CONFIRMED",
        "NEEDS_CLARIFICATION",
        "DRAFT_ORDER",
        "ORDER_ANNEX",
        "SUPPORTING_DOCUMENT",
        "DUPLICATE",
        "NOT_AN_ORDER",
    }
)
TERMINAL_REVIEW_OUTCOMES = REVIEW_OUTCOMES - {"NEEDS_CLARIFICATION"}
INITIAL_REVIEW_STATES = (
    "REQUISITES_PRECONFIRMED",
    "NEEDS_REQUISITES",
    "NEEDS_DOCUMENT_TYPE",
    "POSSIBLE_NON_ORDER",
)


def _safe_relative_path(value: object) -> str:
    candidate = str(value or "").strip()
    normalized = candidate.replace("\\", "/")
    windows_path = PureWindowsPath(candidate)
    if (
        not candidate
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or PurePosixPath(normalized).is_absolute()
        or ".." in PurePosixPath(normalized).parts
    ):
        return ""
    return candidate


def _excel_row_expression(alias: str = "r") -> str:
    return (
        f"CASE WHEN {alias}.source_row_number ~ '^[0-9]+$' "
        f"THEN {alias}.source_row_number::integer + 1 ELSE 0 END"
    )


def list_latest_archive_review(
    *,
    search: str | None = None,
    initial_review_state: str | None = None,
    review_outcome: str | None = None,
    archive_section: str | None = None,
    only_missing_requisites: bool = False,
    only_duplicate_sha: bool = False,
    only_order_298: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 200))
    safe_offset = max(0, int(offset))

    with engine.connect() as conn:
        available = conn.execute(
            text("SELECT to_regclass('public.operational_order_import_batches') IS NOT NULL")
        ).scalar()
        if not available:
            return _empty_result(limit=safe_limit, offset=safe_offset)

        batch = conn.execute(
            text(
                """
                SELECT
                    id AS batch_id,
                    batch_fingerprint,
                    source_manifest_name,
                    created_at AS imported_at,
                    created_by_user_id AS actor_user_id
                FROM public.operational_order_import_batches
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            )
        ).mappings().first()
        if batch is None:
            return _empty_result(limit=safe_limit, offset=safe_offset)

        batch_id = int(batch["batch_id"])
        state_rows = conn.execute(
            text(
                """
                SELECT initial_review_state, COUNT(1) AS count
                FROM public.operational_order_import_rows
                WHERE batch_id = :batch_id
                GROUP BY initial_review_state
                """
            ),
            {"batch_id": batch_id},
        ).mappings().all()
        state_counts = {state: 0 for state in INITIAL_REVIEW_STATES}
        state_counts.update({str(row["initial_review_state"]): int(row["count"]) for row in state_rows})

        outcome_rows = conn.execute(
            text(
                """
                SELECT review_outcome, COUNT(1) AS count
                FROM public.operational_order_import_rows
                WHERE batch_id = :batch_id AND review_outcome IS NOT NULL
                GROUP BY review_outcome
                """
            ),
            {"batch_id": batch_id},
        ).mappings().all()
        outcome_counts = {outcome: 0 for outcome in sorted(REVIEW_OUTCOMES)}
        outcome_counts.update({str(row["review_outcome"]): int(row["count"]) for row in outcome_rows})

        extension_rows = conn.execute(
            text(
                """
                SELECT file_extension, COUNT(1) AS count
                FROM public.operational_order_import_rows
                WHERE batch_id = :batch_id
                GROUP BY file_extension
                ORDER BY file_extension
                """
            ),
            {"batch_id": batch_id},
        ).mappings().all()
        extension_counts = {str(row["file_extension"]): int(row["count"]) for row in extension_rows}

        sections = [
            str(value)
            for value in conn.execute(
                text(
                    """
                    SELECT DISTINCT archive_section
                    FROM public.operational_order_import_rows
                    WHERE batch_id = :batch_id
                    ORDER BY archive_section
                    """
                ),
                {"batch_id": batch_id},
            ).scalars()
        ]
        total_records = sum(state_counts.values())
        preconfirmed = state_counts.get("REQUISITES_PRECONFIRMED", 0)
        duplicate_rows = _problem_excel_rows(conn, batch_id=batch_id, duplicate_sha=True)
        repeated_298_rows = _problem_excel_rows(conn, batch_id=batch_id, order_298=True)

        clauses = ["r.batch_id = :batch_id"]
        params: dict[str, Any] = {
            "batch_id": batch_id,
            "limit": safe_limit,
            "offset": safe_offset,
        }
        if search and search.strip():
            escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            clauses.append(
                "(r.source_filename ILIKE :search ESCAPE '\\' "
                "OR COALESCE(r.source_order_number, '') ILIKE :search ESCAPE '\\' "
                "OR r.source_event_type ILIKE :search ESCAPE '\\' "
                "OR r.relative_path ILIKE :search ESCAPE '\\')"
            )
            params["search"] = f"%{escaped}%"
        if initial_review_state:
            clauses.append("r.initial_review_state = :initial_review_state")
            params["initial_review_state"] = initial_review_state
        if review_outcome == "UNREVIEWED":
            clauses.append("r.review_outcome IS NULL")
        elif review_outcome:
            clauses.append("r.review_outcome = :review_outcome")
            params["review_outcome"] = review_outcome
        if archive_section:
            clauses.append("r.archive_section = :archive_section")
            params["archive_section"] = archive_section
        if only_missing_requisites:
            clauses.append("(r.source_order_number IS NULL OR r.source_order_date IS NULL)")
        duplicate_predicate = (
            "EXISTS (SELECT 1 FROM public.operational_order_import_rows duplicate "
            "WHERE duplicate.batch_id = r.batch_id "
            "AND duplicate.file_sha256 = r.file_sha256 AND duplicate.id <> r.id)"
        )
        if only_duplicate_sha:
            clauses.append(duplicate_predicate)
        if only_order_298:
            clauses.append("r.source_order_number = :order_298")
            params["order_298"] = "298-ө"

        where_sql = " AND ".join(clauses)
        excel_row_sql = _excel_row_expression()
        rows = conn.execute(
            text(
                f"""
                SELECT
                    r.id AS row_id,
                    {excel_row_sql} AS excel_row,
                    r.archive_section,
                    r.source_filename AS file_name,
                    r.source_status,
                    r.initial_review_state,
                    r.source_order_number AS order_number,
                    r.source_order_date AS order_date,
                    r.source_event_type AS subject,
                    r.relative_path,
                    {duplicate_predicate} AS duplicate_sha,
                    COALESCE(r.source_order_number = '298-ө', FALSE) AS repeated_298,
                    r.official_document_id,
                    r.review_outcome,
                    COALESCE(NULLIF(BTRIM(reviewer.full_name), ''), NULLIF(BTRIM(reviewer.login), ''))
                        AS reviewer_display_name,
                    r.reviewed_at,
                    r.version
                FROM public.operational_order_import_rows r
                LEFT JOIN public.users reviewer ON reviewer.user_id = r.reviewed_by_user_id
                WHERE {where_sql}
                ORDER BY {excel_row_sql}, r.id
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()
        filtered_total = conn.execute(
            text(
                f"""
                SELECT COUNT(1)
                FROM public.operational_order_import_rows r
                WHERE {where_sql}
                """
            ),
            params,
        ).scalar()

    items = []
    for row in rows:
        item = dict(row)
        item["relative_path"] = _safe_relative_path(item["relative_path"])
        items.append(item)
    return {
        "batch": dict(batch),
        "stats": {
            "initial_quality": {
                "total": total_records,
                "preconfirmed": preconfirmed,
                "incomplete": total_records - preconfirmed,
                "state_counts": state_counts,
            },
            "work_queue": {
                "pending_review": total_records - sum(outcome_counts.values()),
                "needs_clarification": outcome_counts["NEEDS_CLARIFICATION"],
                "completed_review": sum(outcome_counts[value] for value in TERMINAL_REVIEW_OUTCOMES),
                "outcome_counts": outcome_counts,
            },
            "archive_section_count": len(sections),
            "extension_counts": extension_counts,
            "duplicate_sha_excel_rows": duplicate_rows,
            "repeated_298_excel_rows": repeated_298_rows,
        },
        "sections": sections,
        "items": items,
        "total": int(filtered_total or 0),
        "limit": safe_limit,
        "offset": safe_offset,
    }


def get_archive_review_row(*, row_id: int) -> dict[str, Any]:
    with engine.connect() as conn:
        row = _fetch_archive_review_row(conn, row_id=int(row_id))
    if row is None:
        raise OperationalOrderArchiveRowNotFoundError(f"Archive row {row_id} not found.")
    return row


def save_archive_review(
    *,
    row_id: int,
    actor_user_id: int,
    expected_version: int,
    review_outcome: str,
    confirmed_document_type: str | None = None,
    confirmed_order_number: str | None = None,
    confirmed_order_date: object = None,
    confirmed_subject: str | None = None,
    review_comment: str | None = None,
) -> dict[str, Any]:
    outcome = str(review_outcome or "").strip().upper()
    if outcome not in REVIEW_OUTCOMES:
        raise OperationalOrderValidationError("Unsupported archive review outcome.")
    document_type = _normalized_text(confirmed_document_type, max_length=200)
    order_number = _normalized_text(confirmed_order_number, max_length=100)
    subject = _normalized_text(confirmed_subject, max_length=1000)
    comment = _normalized_text(review_comment, max_length=2000)
    if outcome == "CONFIRMED" and not all((document_type, order_number, confirmed_order_date, subject)):
        raise OperationalOrderValidationError(
            "Document type, order number, order date and subject are required for confirmation."
        )
    if outcome != "CONFIRMED" and not comment:
        raise OperationalOrderValidationError("Review comment is required for this outcome.")
    if outcome != "CONFIRMED":
        document_type = None
        order_number = None
        confirmed_order_date = None
        subject = None

    with engine.begin() as conn:
        updated = conn.execute(
            text(
                """
                UPDATE public.operational_order_import_rows
                SET confirmed_document_type = :confirmed_document_type,
                    confirmed_order_number = :confirmed_order_number,
                    confirmed_order_date = :confirmed_order_date,
                    confirmed_subject = :confirmed_subject,
                    review_outcome = :review_outcome,
                    review_comment = :review_comment,
                    reviewed_by_user_id = :actor_user_id,
                    reviewed_at = clock_timestamp(),
                    version = version + 1
                WHERE id = :row_id
                  AND version = :expected_version
                  AND (
                      review_outcome IS NULL
                      OR (
                          review_outcome = 'NEEDS_CLARIFICATION'
                          AND :review_outcome IN (
                              'CONFIRMED', 'DRAFT_ORDER', 'ORDER_ANNEX',
                              'SUPPORTING_DOCUMENT', 'DUPLICATE', 'NOT_AN_ORDER'
                          )
                      )
                  )
                RETURNING id
                """
            ),
            {
                "row_id": int(row_id),
                "actor_user_id": int(actor_user_id),
                "expected_version": int(expected_version),
                "review_outcome": outcome,
                "confirmed_document_type": document_type,
                "confirmed_order_number": order_number,
                "confirmed_order_date": confirmed_order_date,
                "confirmed_subject": subject,
                "review_comment": comment,
            },
        ).first()
        if updated is None:
            current = conn.execute(
                text("SELECT version, review_outcome FROM public.operational_order_import_rows WHERE id = :row_id"),
                {"row_id": int(row_id)},
            ).mappings().first()
            if current is None:
                raise OperationalOrderArchiveRowNotFoundError(f"Archive row {row_id} not found.")
            if int(current["version"]) != int(expected_version):
                raise OperationalOrderArchiveReviewConflictError("Archive row version conflict.")
            raise OperationalOrderArchiveReviewConflictError("Completed archive review cannot be changed.")
        result = _fetch_archive_review_row(conn, row_id=int(row_id))
        if result is None:
            raise OperationalOrderArchiveRowNotFoundError(f"Archive row {row_id} not found.")
        return result


def _normalized_text(value: object, *, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise OperationalOrderValidationError(f"Text exceeds maximum length {max_length}.")
    return normalized


def _fetch_archive_review_row(conn, *, row_id: int) -> dict[str, Any] | None:
    duplicate_predicate = (
        "EXISTS (SELECT 1 FROM public.operational_order_import_rows duplicate "
        "WHERE duplicate.batch_id = r.batch_id "
        "AND duplicate.file_sha256 = r.file_sha256 AND duplicate.id <> r.id)"
    )
    row = conn.execute(
        text(
            f"""
            SELECT r.id AS row_id,
                   {_excel_row_expression()} AS excel_row,
                   r.archive_section,
                   r.source_filename AS file_name,
                   r.source_document_type,
                   r.source_status,
                   r.initial_review_state,
                   r.source_order_number AS order_number,
                   r.source_order_date AS order_date,
                   r.source_event_type AS subject,
                   r.relative_path,
                   {duplicate_predicate} AS duplicate_sha,
                   COALESCE(r.source_order_number = '298-ө', FALSE) AS repeated_298,
                   r.official_document_id,
                   r.confirmed_document_type,
                   r.confirmed_order_number,
                   r.confirmed_order_date,
                   r.confirmed_subject,
                   r.review_outcome,
                   r.review_comment,
                   COALESCE(NULLIF(BTRIM(reviewer.full_name), ''), NULLIF(BTRIM(reviewer.login), ''))
                       AS reviewer_display_name,
                   r.reviewed_at,
                   r.version
            FROM public.operational_order_import_rows r
            LEFT JOIN public.users reviewer ON reviewer.user_id = r.reviewed_by_user_id
            WHERE r.id = :row_id
            """
        ),
        {"row_id": int(row_id)},
    ).mappings().first()
    if row is None:
        return None
    result = dict(row)
    result["relative_path"] = _safe_relative_path(result["relative_path"])
    return result


def _problem_excel_rows(conn, *, batch_id: int, duplicate_sha: bool = False, order_298: bool = False) -> list[int]:
    clauses = ["r.batch_id = :batch_id", "r.source_row_number ~ '^[0-9]+$'"]
    params: dict[str, Any] = {"batch_id": int(batch_id)}
    if duplicate_sha:
        clauses.append(
            "EXISTS (SELECT 1 FROM public.operational_order_import_rows duplicate "
            "WHERE duplicate.batch_id = r.batch_id "
            "AND duplicate.file_sha256 = r.file_sha256 AND duplicate.id <> r.id)"
        )
    if order_298:
        clauses.append("r.source_order_number = :order_298")
        params["order_298"] = "298-ө"
    values = conn.execute(
        text(
            f"""
            SELECT {_excel_row_expression()} AS excel_row
            FROM public.operational_order_import_rows r
            WHERE {' AND '.join(clauses)}
            ORDER BY excel_row, r.id
            """
        ),
        params,
    ).scalars()
    return [int(value) for value in values]


def _empty_result(*, limit: int, offset: int) -> dict[str, Any]:
    return {
        "batch": None,
        "stats": None,
        "sections": [],
        "items": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
    }
