"""HR import control list persistent storage and business import codes.

Revision ID: a1b2c3d4e5f7
Revises: z5a6b7c8d9e0f1
Create Date: 2026-07-19 08:15:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "z5a6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.hr_import_batches
            ADD COLUMN IF NOT EXISTS import_code TEXT NULL
        """
    )
    op.execute(
        """
        UPDATE public.hr_import_batches
        SET import_code = 'legacy-' || batch_id::text
        WHERE import_code IS NULL OR trim(import_code) = ''
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_import_batches
            ALTER COLUMN import_code SET NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hr_import_batches_import_code
            ON public.hr_import_batches (import_code)
        """
    )

    op.execute(
        """
        ALTER TABLE public.hr_source_files
            ADD COLUMN IF NOT EXISTS technical_filename TEXT NULL,
            ADD COLUMN IF NOT EXISTS source_last_modified_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        """
        UPDATE public.hr_source_files
        SET technical_filename = split_part(storage_ref, '/', -1)
        WHERE technical_filename IS NULL OR trim(technical_filename) = ''
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_source_files
            ALTER COLUMN technical_filename SET NOT NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_hsf_technical_filename_nonempty'
            ) THEN
                ALTER TABLE public.hr_source_files
                    ADD CONSTRAINT chk_hsf_technical_filename_nonempty
                        CHECK (length(trim(technical_filename)) > 0);
            END IF;
        END
        $$;
        """
    )
    op.execute("DROP INDEX IF EXISTS public.uq_hsf_sha256_report_month")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.uq_hr_import_batches_import_code")
    op.execute(
        """
        ALTER TABLE public.hr_import_batches
            DROP COLUMN IF EXISTS import_code
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_source_files
            DROP CONSTRAINT IF EXISTS chk_hsf_technical_filename_nonempty
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_source_files
            DROP COLUMN IF EXISTS technical_filename,
            DROP COLUMN IF EXISTS source_last_modified_at
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hsf_sha256_report_month
            ON public.hr_source_files (content_sha256, report_month, source_system)
        """
    )
