"""ADR-038 Phase A.1 — import provenance and audit columns on employee overrides.

Revision ID: l5e6f7a8b9c0
Revises: k4d5e6f7a8b9
Create Date: 2026-06-17
"""
from __future__ import annotations

from alembic import op

revision = "l5e6f7a8b9c0"
down_revision = "k4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.employee_import_profile_overrides
            ADD COLUMN IF NOT EXISTS base_batch_id BIGINT NULL
                REFERENCES public.hr_import_batches(batch_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS base_row_id BIGINT NULL
                REFERENCES public.hr_import_rows(row_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS base_imported_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS created_by BIGINT NULL
                REFERENCES public.users(user_id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_import_profile_overrides_base_batch
            ON public.employee_import_profile_overrides (base_batch_id)
        """
    )
    op.execute(
        """
        UPDATE public.employee_import_profile_overrides o
        SET
            base_batch_id = src.batch_id,
            base_row_id = src.row_id,
            base_imported_at = src.imported_at
        FROM (
            SELECT DISTINCT ON (r.employee_id)
                r.employee_id,
                r.batch_id,
                r.row_id,
                b.imported_at
            FROM public.hr_import_rows r
            JOIN public.hr_import_batches b ON b.batch_id = r.batch_id
            WHERE r.employee_id IS NOT NULL
            ORDER BY r.employee_id, b.imported_at DESC NULLS LAST, r.row_id DESC
        ) src
        WHERE o.employee_id = src.employee_id
          AND o.base_batch_id IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_employee_import_profile_overrides_base_batch")
    op.execute(
        """
        ALTER TABLE public.employee_import_profile_overrides
            DROP COLUMN IF EXISTS base_batch_id,
            DROP COLUMN IF EXISTS base_row_id,
            DROP COLUMN IF EXISTS base_imported_at,
            DROP COLUMN IF EXISTS created_by
        """
    )
