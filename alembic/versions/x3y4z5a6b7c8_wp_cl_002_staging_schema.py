"""WP-CL-002: control list import staging schema.

Revision ID: x3y4z5a6b7c8
Revises: w2x3y4z5a6b7
Create Date: 2026-07-17 20:35:00.000000

ADR-057 / WP-CL-002: raw workbook staging (run → sheet → row → cell).
Schema only — no mapping, parsing, apply, or PPR mutations.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "x3y4z5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "w2x3y4z5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RUN_STATUSES = ("staged", "failed", "cancelled")
_SHEET_STATUSES = ("analyzed", "excluded")
_PERSONNEL_CATEGORIES = (
    "doctor",
    "nursing_staff",
    "junior_medical_staff",
    "other_staff",
    "unknown",
)
_EMPLOYMENT_MODES = ("primary", "concurrent", "unknown")
_SHEET_PURPOSES = ("personnel_control_list", "declaration", "unknown")
_ROW_KINDS = (
    "empty",
    "header",
    "title",
    "footer",
    "data",
    "section_header",
    "unknown",
)
_INFERRED_TYPES = (
    "empty",
    "text",
    "integer",
    "decimal",
    "excel_date",
    "date_text",
    "iin_candidate",
    "phone_candidate",
    "composite_text",
    "formula",
    "error",
)


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    run_statuses_sql = _sql_tuple(_RUN_STATUSES)
    sheet_statuses_sql = _sql_tuple(_SHEET_STATUSES)
    personnel_categories_sql = _sql_tuple(_PERSONNEL_CATEGORIES)
    employment_modes_sql = _sql_tuple(_EMPLOYMENT_MODES)
    sheet_purposes_sql = _sql_tuple(_SHEET_PURPOSES)
    row_kinds_sql = _sql_tuple(_ROW_KINDS)
    inferred_types_sql = _sql_tuple(_INFERRED_TYPES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.control_list_import_runs (
            import_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source_filename TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            imported_by BIGINT NOT NULL,
            profiler_version TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'staged',
            CONSTRAINT fk_control_list_import_runs_imported_by
                FOREIGN KEY (imported_by)
                REFERENCES public.users(user_id)
                ON DELETE RESTRICT,
            CONSTRAINT chk_control_list_import_runs_source_filename_nonempty
                CHECK (length(trim(source_filename)) > 0),
            CONSTRAINT chk_control_list_import_runs_source_sha256_format
                CHECK (
                    length(source_sha256) = 64
                    AND source_sha256 ~ '^[0-9a-f]{{64}}$'
                ),
            CONSTRAINT chk_control_list_import_runs_profiler_version_nonempty
                CHECK (length(trim(profiler_version)) > 0),
            CONSTRAINT chk_control_list_import_runs_status
                CHECK (status IN ({run_statuses_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_import_runs_status
            ON public.control_list_import_runs (status, imported_at DESC)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_import_runs_source_sha256
            ON public.control_list_import_runs (source_sha256, imported_at DESC)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_import_runs_imported_by
            ON public.control_list_import_runs (imported_by, imported_at DESC)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.control_list_import_sheets (
            sheet_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            import_run_id BIGINT NOT NULL,
            sheet_name TEXT NOT NULL,
            sheet_index INT NOT NULL,
            personnel_category TEXT NOT NULL DEFAULT 'unknown',
            employment_mode TEXT NOT NULL DEFAULT 'unknown',
            sheet_purpose TEXT NOT NULL DEFAULT 'unknown',
            status TEXT NOT NULL DEFAULT 'analyzed',
            CONSTRAINT fk_control_list_import_sheets_run
                FOREIGN KEY (import_run_id)
                REFERENCES public.control_list_import_runs(import_run_id)
                ON DELETE CASCADE,
            CONSTRAINT uq_control_list_import_sheets_run_index
                UNIQUE (import_run_id, sheet_index),
            CONSTRAINT uq_control_list_import_sheets_run_name
                UNIQUE (import_run_id, sheet_name),
            CONSTRAINT chk_control_list_import_sheets_sheet_index_positive
                CHECK (sheet_index >= 0),
            CONSTRAINT chk_control_list_import_sheets_sheet_name_nonempty
                CHECK (length(trim(sheet_name)) > 0),
            CONSTRAINT chk_control_list_import_sheets_personnel_category
                CHECK (personnel_category IN ({personnel_categories_sql})),
            CONSTRAINT chk_control_list_import_sheets_employment_mode
                CHECK (employment_mode IN ({employment_modes_sql})),
            CONSTRAINT chk_control_list_import_sheets_sheet_purpose
                CHECK (sheet_purpose IN ({sheet_purposes_sql})),
            CONSTRAINT chk_control_list_import_sheets_status
                CHECK (status IN ({sheet_statuses_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_import_sheets_run
            ON public.control_list_import_sheets (import_run_id, sheet_index)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_import_sheets_run_status
            ON public.control_list_import_sheets (import_run_id, status)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.control_list_import_rows (
            row_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            sheet_id BIGINT NOT NULL,
            excel_row_number INT NOT NULL,
            row_kind TEXT NOT NULL DEFAULT 'unknown',
            section_key TEXT NULL,
            section_caption TEXT NULL,
            CONSTRAINT fk_control_list_import_rows_sheet
                FOREIGN KEY (sheet_id)
                REFERENCES public.control_list_import_sheets(sheet_id)
                ON DELETE CASCADE,
            CONSTRAINT uq_control_list_import_rows_sheet_row
                UNIQUE (sheet_id, excel_row_number),
            CONSTRAINT chk_control_list_import_rows_excel_row_number_positive
                CHECK (excel_row_number >= 1),
            CONSTRAINT chk_control_list_import_rows_row_kind
                CHECK (row_kind IN ({row_kinds_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_import_rows_sheet
            ON public.control_list_import_rows (sheet_id, excel_row_number)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_import_rows_sheet_kind
            ON public.control_list_import_rows (sheet_id, row_kind)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.control_list_import_cells (
            cell_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            row_id BIGINT NOT NULL,
            column_letter TEXT NOT NULL,
            column_index INT NOT NULL,
            raw_header TEXT NULL,
            raw_value TEXT NULL,
            normalized_text TEXT NULL,
            inferred_type TEXT NOT NULL DEFAULT 'empty',
            issue_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
            semantic_hint TEXT NULL,
            is_composite BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT fk_control_list_import_cells_row
                FOREIGN KEY (row_id)
                REFERENCES public.control_list_import_rows(row_id)
                ON DELETE CASCADE,
            CONSTRAINT uq_control_list_import_cells_row_column
                UNIQUE (row_id, column_index),
            CONSTRAINT chk_control_list_import_cells_column_index_positive
                CHECK (column_index >= 1),
            CONSTRAINT chk_control_list_import_cells_column_letter_nonempty
                CHECK (length(trim(column_letter)) > 0),
            CONSTRAINT chk_control_list_import_cells_inferred_type
                CHECK (inferred_type IN ({inferred_types_sql})),
            CONSTRAINT chk_control_list_import_cells_issue_codes_array
                CHECK (jsonb_typeof(issue_codes) = 'array')
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_import_cells_row
            ON public.control_list_import_cells (row_id, column_index)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_import_cells_semantic_hint
            ON public.control_list_import_cells (semantic_hint)
            WHERE semantic_hint IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.control_list_import_cells CASCADE")
    op.execute("DROP TABLE IF EXISTS public.control_list_import_rows CASCADE")
    op.execute("DROP TABLE IF EXISTS public.control_list_import_sheets CASCADE")
    op.execute("DROP TABLE IF EXISTS public.control_list_import_runs CASCADE")
