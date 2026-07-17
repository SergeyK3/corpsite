"""WP-CL-003: control list mapping profiles.

Revision ID: y4z5a6b7c8d9e0
Revises: x3y4z5a6b7c8
Create Date: 2026-07-17 22:55:00.000000

ADR-057 / WP-CL-003: configurable mapping profiles (profile → sheet → column).
Schema only — no profile application, candidates, apply, or PPR mutations.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "y4z5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "x3y4z5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROFILE_STATUSES = ("draft", "active", "archived")
_PERSONNEL_CATEGORIES = (
    "doctor",
    "nursing_staff",
    "junior_medical_staff",
    "other_staff",
    "unknown",
)
_EMPLOYMENT_MODES = ("primary", "concurrent", "unknown")
_SHEET_PURPOSES = ("personnel_control_list", "declaration", "unknown")
_SEMANTIC_FIELDS = (
    "person.full_name",
    "person.birth_date",
    "person.iin",
    "person.sex",
    "person.nationality_raw",
    "person.phone",
    "person.awards",
    "person.notes",
    "employment.department_name",
    "employment.position_title",
    "employment.started_at",
    "education.records",
    "training.records",
    "qualification.category",
    "qualification.degree",
)
_PARSER_CODES = (
    "text.plain",
    "text.composite_numbered",
    "person.full_name",
    "identity.iin",
    "identity.phone",
    "date.excel_serial",
    "date.text",
    "employment.department",
    "employment.position",
    "employment.started_at",
    "records.education",
    "records.training",
    "qualification.category",
    "qualification.degree",
    "person.sex",
    "person.nationality",
    "text.awards",
    "text.notes",
)


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    profile_statuses_sql = _sql_tuple(_PROFILE_STATUSES)
    personnel_categories_sql = _sql_tuple(_PERSONNEL_CATEGORIES)
    employment_modes_sql = _sql_tuple(_EMPLOYMENT_MODES)
    sheet_purposes_sql = _sql_tuple(_SHEET_PURPOSES)
    semantic_fields_sql = _sql_tuple(_SEMANTIC_FIELDS)
    parser_codes_sql = _sql_tuple(_PARSER_CODES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.control_list_mapping_profiles (
            profile_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            profile_code TEXT NOT NULL,
            profile_version INT NOT NULL,
            profile_name TEXT NOT NULL,
            description TEXT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by BIGINT NOT NULL,
            updated_at TIMESTAMPTZ NULL,
            CONSTRAINT fk_control_list_mapping_profiles_created_by
                FOREIGN KEY (created_by)
                REFERENCES public.users(user_id)
                ON DELETE RESTRICT,
            CONSTRAINT uq_control_list_mapping_profiles_code_version
                UNIQUE (profile_code, profile_version),
            CONSTRAINT chk_control_list_mapping_profiles_code_nonempty
                CHECK (length(trim(profile_code)) > 0),
            CONSTRAINT chk_control_list_mapping_profiles_name_nonempty
                CHECK (length(trim(profile_name)) > 0),
            CONSTRAINT chk_control_list_mapping_profiles_version_positive
                CHECK (profile_version >= 1),
            CONSTRAINT chk_control_list_mapping_profiles_status
                CHECK (status IN ({profile_statuses_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_control_list_mapping_profiles_active_code
            ON public.control_list_mapping_profiles (profile_code)
            WHERE status = 'active'
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_mapping_profiles_status
            ON public.control_list_mapping_profiles (status, profile_code, profile_version DESC)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_mapping_profiles_created_by
            ON public.control_list_mapping_profiles (created_by, created_at DESC)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.control_list_mapping_profile_sheets (
            profile_sheet_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            profile_id BIGINT NOT NULL,
            sheet_name TEXT NOT NULL,
            personnel_category TEXT NOT NULL DEFAULT 'unknown',
            employment_mode TEXT NOT NULL DEFAULT 'unknown',
            sheet_purpose TEXT NOT NULL DEFAULT 'unknown',
            header_row_override INT NULL,
            CONSTRAINT fk_control_list_mapping_profile_sheets_profile
                FOREIGN KEY (profile_id)
                REFERENCES public.control_list_mapping_profiles(profile_id)
                ON DELETE CASCADE,
            CONSTRAINT uq_control_list_mapping_profile_sheets_profile_name
                UNIQUE (profile_id, sheet_name),
            CONSTRAINT chk_control_list_mapping_profile_sheets_sheet_name_nonempty
                CHECK (length(trim(sheet_name)) > 0),
            CONSTRAINT chk_control_list_mapping_profile_sheets_personnel_category
                CHECK (personnel_category IN ({personnel_categories_sql})),
            CONSTRAINT chk_control_list_mapping_profile_sheets_employment_mode
                CHECK (employment_mode IN ({employment_modes_sql})),
            CONSTRAINT chk_control_list_mapping_profile_sheets_sheet_purpose
                CHECK (sheet_purpose IN ({sheet_purposes_sql})),
            CONSTRAINT chk_control_list_mapping_profile_sheets_header_row_override
                CHECK (header_row_override IS NULL OR header_row_override >= 1)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_mapping_profile_sheets_profile
            ON public.control_list_mapping_profile_sheets (profile_id, sheet_name)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.control_list_mapping_profile_columns (
            profile_column_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            profile_sheet_id BIGINT NOT NULL,
            column_index INT NOT NULL,
            column_letter TEXT NULL,
            raw_header TEXT NULL,
            semantic_field TEXT NOT NULL,
            parser_code TEXT NOT NULL,
            is_required BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT fk_control_list_mapping_profile_columns_sheet
                FOREIGN KEY (profile_sheet_id)
                REFERENCES public.control_list_mapping_profile_sheets(profile_sheet_id)
                ON DELETE CASCADE,
            CONSTRAINT uq_control_list_mapping_profile_columns_sheet_column
                UNIQUE (profile_sheet_id, column_index),
            CONSTRAINT chk_control_list_mapping_profile_columns_column_index_positive
                CHECK (column_index >= 1),
            CONSTRAINT chk_control_list_mapping_profile_columns_semantic_field
                CHECK (semantic_field IN ({semantic_fields_sql})),
            CONSTRAINT chk_control_list_mapping_profile_columns_parser_code
                CHECK (parser_code IN ({parser_codes_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_mapping_profile_columns_sheet
            ON public.control_list_mapping_profile_columns (profile_sheet_id, column_index)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_mapping_profile_columns_semantic_field
            ON public.control_list_mapping_profile_columns (semantic_field)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.control_list_mapping_profile_columns CASCADE")
    op.execute("DROP TABLE IF EXISTS public.control_list_mapping_profile_sheets CASCADE")
    op.execute("DROP TABLE IF EXISTS public.control_list_mapping_profiles CASCADE")
