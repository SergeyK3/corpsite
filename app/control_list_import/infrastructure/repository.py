"""Control List import staging persistence (WP-CL-002).

Append-only staging writes. Classification and semantic_hint values persisted here
are profiler snapshots for the import_run — not canonical mapping.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.control_list_import import (
    EMPLOYMENT_MODE_PRIMARY,
    INFERRED_TYPE_TEXT,
    PERSONNEL_CATEGORY_DOCTOR,
    ROW_KIND_DATA,
    RUN_STATUS_STAGED,
    SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
    SHEET_STATUS_ANALYZED,
)


class SqlAlchemyControlListImportStagingRepository:
    """Minimal append-only staging repository without business logic.

    Persists profiler snapshot fields as-is; does not resolve or override canonical mapping.
    """

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def create_run(
        self,
        *,
        source_filename: str,
        source_sha256: str,
        imported_by: int,
        profiler_version: str,
        status: str = RUN_STATUS_STAGED,
    ) -> int:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.control_list_import_runs (
                    source_filename,
                    source_sha256,
                    imported_by,
                    profiler_version,
                    status
                )
                VALUES (
                    :source_filename,
                    :source_sha256,
                    :imported_by,
                    :profiler_version,
                    :status
                )
                RETURNING import_run_id
                """
            ),
            {
                "source_filename": source_filename,
                "source_sha256": source_sha256,
                "imported_by": int(imported_by),
                "profiler_version": profiler_version,
                "status": status,
            },
        ).one()
        return int(row.import_run_id)

    def create_sheet(
        self,
        *,
        import_run_id: int,
        sheet_name: str,
        sheet_index: int,
        personnel_category: str = PERSONNEL_CATEGORY_DOCTOR,
        employment_mode: str = EMPLOYMENT_MODE_PRIMARY,
        sheet_purpose: str = SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
        status: str = SHEET_STATUS_ANALYZED,
    ) -> int:
        """Persist sheet with profiler classification snapshot (not canonical mapping)."""
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.control_list_import_sheets (
                    import_run_id,
                    sheet_name,
                    sheet_index,
                    personnel_category,
                    employment_mode,
                    sheet_purpose,
                    status
                )
                VALUES (
                    :import_run_id,
                    :sheet_name,
                    :sheet_index,
                    :personnel_category,
                    :employment_mode,
                    :sheet_purpose,
                    :status
                )
                RETURNING sheet_id
                """
            ),
            {
                "import_run_id": int(import_run_id),
                "sheet_name": sheet_name,
                "sheet_index": int(sheet_index),
                "personnel_category": personnel_category,
                "employment_mode": employment_mode,
                "sheet_purpose": sheet_purpose,
                "status": status,
            },
        ).one()
        return int(row.sheet_id)

    def create_row(
        self,
        *,
        sheet_id: int,
        excel_row_number: int,
        row_kind: str = ROW_KIND_DATA,
        section_key: str | None = None,
        section_caption: str | None = None,
    ) -> int:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.control_list_import_rows (
                    sheet_id,
                    excel_row_number,
                    row_kind,
                    section_key,
                    section_caption
                )
                VALUES (
                    :sheet_id,
                    :excel_row_number,
                    :row_kind,
                    :section_key,
                    :section_caption
                )
                RETURNING row_id
                """
            ),
            {
                "sheet_id": int(sheet_id),
                "excel_row_number": int(excel_row_number),
                "row_kind": row_kind,
                "section_key": section_key,
                "section_caption": section_caption,
            },
        ).one()
        return int(row.row_id)

    def create_cell(
        self,
        *,
        row_id: int,
        column_letter: str,
        column_index: int,
        raw_header: str | None = None,
        raw_value: str | None = None,
        normalized_text: str | None = None,
        inferred_type: str = INFERRED_TYPE_TEXT,
        issue_codes: list[str] | None = None,
        semantic_hint: str | None = None,
        is_composite: bool = False,
    ) -> int:
        """Persist cell; ``semantic_hint`` is profiler recommendation, not canonical mapping."""
        codes = issue_codes or []
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.control_list_import_cells (
                    row_id,
                    column_letter,
                    column_index,
                    raw_header,
                    raw_value,
                    normalized_text,
                    inferred_type,
                    issue_codes,
                    semantic_hint,
                    is_composite
                )
                VALUES (
                    :row_id,
                    :column_letter,
                    :column_index,
                    :raw_header,
                    :raw_value,
                    :normalized_text,
                    :inferred_type,
                    CAST(:issue_codes AS jsonb),
                    :semantic_hint,
                    :is_composite
                )
                RETURNING cell_id
                """
            ),
            {
                "row_id": int(row_id),
                "column_letter": column_letter,
                "column_index": int(column_index),
                "raw_header": raw_header,
                "raw_value": raw_value,
                "normalized_text": normalized_text,
                "inferred_type": inferred_type,
                "issue_codes": json.dumps(codes),
                "semantic_hint": semantic_hint,
                "is_composite": bool(is_composite),
            },
        ).one()
        return int(row.cell_id)
