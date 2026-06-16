"""HR import Phase 2C — extend document candidates for training normalization.

Revision ID: e2c4f8a1b3d5
Revises: d3e4f5a6b7c8
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op

revision = "e2c4f8a1b3d5"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.hr_import_document_candidates
            ADD COLUMN IF NOT EXISTS batch_id BIGINT NULL,
            ADD COLUMN IF NOT EXISTS employee_identity_id BIGINT NULL,
            ADD COLUMN IF NOT EXISTS full_name TEXT NULL,
            ADD COLUMN IF NOT EXISTS iin TEXT NULL,
            ADD COLUMN IF NOT EXISTS department TEXT NULL,
            ADD COLUMN IF NOT EXISTS position TEXT NULL,
            ADD COLUMN IF NOT EXISTS document_kind TEXT NOT NULL DEFAULT 'training',
            ADD COLUMN IF NOT EXISTS title TEXT NULL,
            ADD COLUMN IF NOT EXISTS organization TEXT NULL,
            ADD COLUMN IF NOT EXISTS parsed_issued_at DATE NULL,
            ADD COLUMN IF NOT EXISTS specialty TEXT NULL,
            ADD COLUMN IF NOT EXISTS category TEXT NULL,
            ADD COLUMN IF NOT EXISTS certificate_number TEXT NULL,
            ADD COLUMN IF NOT EXISTS raw_text TEXT NOT NULL DEFAULT '',
            ADD COLUMN IF NOT EXISTS source_sheet TEXT NULL,
            ADD COLUMN IF NOT EXISTS source_row INT NULL,
            ADD COLUMN IF NOT EXISTS external_url TEXT NULL,
            ADD COLUMN IF NOT EXISTS storage_type TEXT NULL,
            ADD COLUMN IF NOT EXISTS storage_path TEXT NULL,
            ADD COLUMN IF NOT EXISTS fragment_index INT NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS parse_method TEXT NULL DEFAULT 'regex_v1'
        """
    )

    op.execute(
        """
        UPDATE public.hr_import_document_candidates c
        SET batch_id = r.batch_id
        FROM public.hr_import_rows r
        WHERE c.row_id = r.row_id
          AND c.batch_id IS NULL
        """
    )

    op.execute(
        """
        ALTER TABLE public.hr_import_document_candidates
            ALTER COLUMN batch_id SET NOT NULL
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_hr_import_document_candidates_batch'
            ) THEN
                ALTER TABLE public.hr_import_document_candidates
                    ADD CONSTRAINT fk_hr_import_document_candidates_batch
                    FOREIGN KEY (batch_id)
                    REFERENCES public.hr_import_batches(batch_id)
                    ON DELETE CASCADE;
            END IF;
        END $$
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_hr_import_document_candidates_identity'
            ) THEN
                ALTER TABLE public.hr_import_document_candidates
                    ADD CONSTRAINT fk_hr_import_document_candidates_identity
                    FOREIGN KEY (employee_identity_id)
                    REFERENCES public.employee_identities(identity_id)
                    ON DELETE SET NULL;
            END IF;
        END $$
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_hr_import_document_candidates_kind'
            ) THEN
                ALTER TABLE public.hr_import_document_candidates
                    ADD CONSTRAINT chk_hr_import_document_candidates_kind
                    CHECK (document_kind IN ('training', 'certification'));
            END IF;
        END $$
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_hr_import_document_candidates_storage_type'
            ) THEN
                ALTER TABLE public.hr_import_document_candidates
                    ADD CONSTRAINT chk_hr_import_document_candidates_storage_type
                    CHECK (
                        storage_type IS NULL
                        OR storage_type IN ('url', 'google_drive', 'network_share', 'none')
                    );
            END IF;
        END $$
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_document_candidates_batch
            ON public.hr_import_document_candidates (batch_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_document_candidates_batch_kind
            ON public.hr_import_document_candidates (batch_id, document_kind)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_document_candidates_batch_status
            ON public.hr_import_document_candidates (batch_id, review_status)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_hr_import_document_candidates_batch_status")
    op.execute("DROP INDEX IF EXISTS public.ix_hr_import_document_candidates_batch_kind")
    op.execute("DROP INDEX IF EXISTS public.ix_hr_import_document_candidates_batch")

    op.execute(
        """
        ALTER TABLE public.hr_import_document_candidates
            DROP CONSTRAINT IF EXISTS chk_hr_import_document_candidates_storage_type,
            DROP CONSTRAINT IF EXISTS chk_hr_import_document_candidates_kind,
            DROP CONSTRAINT IF EXISTS fk_hr_import_document_candidates_identity,
            DROP CONSTRAINT IF EXISTS fk_hr_import_document_candidates_batch,
            DROP COLUMN IF EXISTS parse_method,
            DROP COLUMN IF EXISTS fragment_index,
            DROP COLUMN IF EXISTS storage_path,
            DROP COLUMN IF EXISTS storage_type,
            DROP COLUMN IF EXISTS external_url,
            DROP COLUMN IF EXISTS source_row,
            DROP COLUMN IF EXISTS source_sheet,
            DROP COLUMN IF EXISTS raw_text,
            DROP COLUMN IF EXISTS certificate_number,
            DROP COLUMN IF EXISTS category,
            DROP COLUMN IF EXISTS specialty,
            DROP COLUMN IF EXISTS parsed_issued_at,
            DROP COLUMN IF EXISTS organization,
            DROP COLUMN IF EXISTS title,
            DROP COLUMN IF EXISTS document_kind,
            DROP COLUMN IF EXISTS position,
            DROP COLUMN IF EXISTS department,
            DROP COLUMN IF EXISTS iin,
            DROP COLUMN IF EXISTS full_name,
            DROP COLUMN IF EXISTS employee_identity_id,
            DROP COLUMN IF EXISTS batch_id
        """
    )
