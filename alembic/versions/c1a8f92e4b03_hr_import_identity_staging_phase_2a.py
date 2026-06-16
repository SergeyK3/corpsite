"""hr import identity and staging phase 2a

Revision ID: c1a8f92e4b03
Revises: f2b3c4d5e6a7
Create Date: 2026-06-16 18:00:00.000000

ADR-038 Phase 2A: employee_identities, hr_import_* staging,
org_unit_aliases, position_aliases. Schema only — no seeds.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c1a8f92e4b03"
down_revision: Union[str, Sequence[str], None] = "f2b3c4d5e6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.employee_identities (
            identity_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            employee_id BIGINT NOT NULL,
            identity_type TEXT NOT NULL,
            identity_value TEXT NOT NULL,
            valid_from DATE NULL,
            valid_to DATE NULL,
            is_primary BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by BIGINT NULL,
            CONSTRAINT fk_employee_identities_employee
                FOREIGN KEY (employee_id)
                REFERENCES public.employees(employee_id)
                ON DELETE CASCADE,
            CONSTRAINT fk_employee_identities_created_by
                FOREIGN KEY (created_by)
                REFERENCES public.users(user_id)
                ON DELETE SET NULL,
            CONSTRAINT chk_employee_identities_type_nonempty
                CHECK (length(trim(identity_type)) > 0),
            CONSTRAINT chk_employee_identities_value_nonempty
                CHECK (length(trim(identity_value)) > 0)
        )
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_employee_identities_iin_active
            ON public.employee_identities (identity_value)
            WHERE identity_type = 'IIN' AND valid_to IS NULL
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_identities_employee
            ON public.employee_identities (employee_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_identities_type_value
            ON public.employee_identities (identity_type, identity_value)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_import_batches (
            batch_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source_type TEXT NOT NULL,
            file_name TEXT NOT NULL,
            imported_by BIGINT NOT NULL,
            imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            status TEXT NOT NULL DEFAULT 'UPLOADED',
            total_rows INT NOT NULL DEFAULT 0,
            valid_rows INT NOT NULL DEFAULT 0,
            error_rows INT NOT NULL DEFAULT 0,
            CONSTRAINT fk_hr_import_batches_imported_by
                FOREIGN KEY (imported_by)
                REFERENCES public.users(user_id)
                ON DELETE RESTRICT,
            CONSTRAINT chk_hr_import_batches_status
                CHECK (status IN (
                    'UPLOADED', 'PARSED', 'IN_REVIEW', 'APPLY_PENDING',
                    'APPLIED', 'PARTIALLY_APPLIED', 'FAILED', 'CANCELLED'
                )),
            CONSTRAINT chk_hr_import_batches_source_type
                CHECK (length(trim(source_type)) > 0)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_batches_status
            ON public.hr_import_batches (status)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_batches_imported_by
            ON public.hr_import_batches (imported_by)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_import_rows (
            row_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            batch_id BIGINT NOT NULL,
            source_sheet TEXT NOT NULL,
            source_row_number INT NOT NULL,
            raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            normalized_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            match_status TEXT NOT NULL DEFAULT 'REVIEW_REQUIRED',
            review_status TEXT NULL,
            error_codes TEXT[] NULL,
            employee_id BIGINT NULL,
            CONSTRAINT fk_hr_import_rows_batch
                FOREIGN KEY (batch_id)
                REFERENCES public.hr_import_batches(batch_id)
                ON DELETE CASCADE,
            CONSTRAINT fk_hr_import_rows_employee
                FOREIGN KEY (employee_id)
                REFERENCES public.employees(employee_id)
                ON DELETE SET NULL,
            CONSTRAINT uq_hr_import_rows_source
                UNIQUE (batch_id, source_sheet, source_row_number),
            CONSTRAINT chk_hr_import_rows_match_status
                CHECK (match_status IN (
                    'AUTO_MATCH', 'REVIEW_REQUIRED', 'NO_MATCH', 'INVALID_DATA', 'SKIPPED'
                )),
            CONSTRAINT chk_hr_import_rows_review_status
                CHECK (
                    review_status IS NULL
                    OR review_status IN ('PENDING', 'APPROVED', 'REJECTED', 'MERGED')
                )
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_rows_batch
            ON public.hr_import_rows (batch_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_rows_match_status
            ON public.hr_import_rows (batch_id, match_status)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_import_document_candidates (
            candidate_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            row_id BIGINT NOT NULL,
            employee_id BIGINT NULL,
            proposed_document_type TEXT NULL,
            parsed_hours NUMERIC(8, 2) NULL,
            parsed_valid_until DATE NULL,
            confidence_score NUMERIC(5, 4) NULL,
            review_status TEXT NOT NULL DEFAULT 'PENDING',
            created_document_id BIGINT NULL,
            CONSTRAINT fk_hr_import_document_candidates_row
                FOREIGN KEY (row_id)
                REFERENCES public.hr_import_rows(row_id)
                ON DELETE CASCADE,
            CONSTRAINT fk_hr_import_document_candidates_employee
                FOREIGN KEY (employee_id)
                REFERENCES public.employees(employee_id)
                ON DELETE SET NULL,
            CONSTRAINT fk_hr_import_document_candidates_document
                FOREIGN KEY (created_document_id)
                REFERENCES public.employee_documents(document_id)
                ON DELETE SET NULL,
            CONSTRAINT chk_hr_import_document_candidates_hours
                CHECK (parsed_hours IS NULL OR parsed_hours >= 0),
            CONSTRAINT chk_hr_import_document_candidates_confidence
                CHECK (
                    confidence_score IS NULL
                    OR (confidence_score >= 0 AND confidence_score <= 1)
                ),
            CONSTRAINT chk_hr_import_document_candidates_review_status
                CHECK (review_status IN ('PENDING', 'APPROVED', 'REJECTED', 'MERGED'))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_document_candidates_row
            ON public.hr_import_document_candidates (row_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_document_candidates_employee
            ON public.hr_import_document_candidates (employee_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_document_candidates_review
            ON public.hr_import_document_candidates (review_status)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.org_unit_aliases (
            alias_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            org_unit_id BIGINT NOT NULL,
            alias_text TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            CONSTRAINT fk_org_unit_aliases_org_unit
                FOREIGN KEY (org_unit_id)
                REFERENCES public.org_units(unit_id)
                ON DELETE CASCADE,
            CONSTRAINT uq_org_unit_aliases_normalized
                UNIQUE (normalized_alias),
            CONSTRAINT chk_org_unit_aliases_text_nonempty
                CHECK (length(trim(alias_text)) > 0),
            CONSTRAINT chk_org_unit_aliases_normalized_nonempty
                CHECK (length(trim(normalized_alias)) > 0)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_org_unit_aliases_org_unit
            ON public.org_unit_aliases (org_unit_id)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.position_aliases (
            alias_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            position_id BIGINT NOT NULL,
            alias_text TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            CONSTRAINT fk_position_aliases_position
                FOREIGN KEY (position_id)
                REFERENCES public.positions(position_id)
                ON DELETE CASCADE,
            CONSTRAINT uq_position_aliases_normalized
                UNIQUE (normalized_alias),
            CONSTRAINT chk_position_aliases_text_nonempty
                CHECK (length(trim(alias_text)) > 0),
            CONSTRAINT chk_position_aliases_normalized_nonempty
                CHECK (length(trim(normalized_alias)) > 0)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_position_aliases_position
            ON public.position_aliases (position_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.hr_import_document_candidates CASCADE")
    op.execute("DROP TABLE IF EXISTS public.hr_import_rows CASCADE")
    op.execute("DROP TABLE IF EXISTS public.hr_import_batches CASCADE")
    op.execute("DROP TABLE IF EXISTS public.position_aliases CASCADE")
    op.execute("DROP TABLE IF EXISTS public.org_unit_aliases CASCADE")
    op.execute("DROP TABLE IF EXISTS public.employee_identities CASCADE")
