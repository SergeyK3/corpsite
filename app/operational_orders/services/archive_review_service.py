"""Read-only queries for operational-order archive import staging."""
from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from sqlalchemy import text

from app.db.engine import engine


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
        state_counts = {str(row["initial_review_state"]): int(row["count"]) for row in state_rows}

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
                    r.official_document_id
                FROM public.operational_order_import_rows r
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
            "total_records": total_records,
            "preconfirmed_records": preconfirmed,
            "requires_processing": total_records - preconfirmed,
            "archive_section_count": len(sections),
            "state_counts": state_counts,
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
