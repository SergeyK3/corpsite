"""Lifecycle columns for initial baseline source selections + MRD source_batch_id placeholder.

Revision ID: h9i0j1k2l3m4
Revises: g8h9i0j1k2l3
"""
from __future__ import annotations

from alembic import op

revision = "h9i0j1k2l3m4"
down_revision = "g8h9i0j1k2l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.hr_initial_baseline_source_selections
            ADD COLUMN IF NOT EXISTS lifecycle_status TEXT NOT NULL DEFAULT 'ACTIVE',
            ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS consumed_mrd_id BIGINT NULL
                REFERENCES public.hr_monthly_references (mrd_id) ON DELETE RESTRICT
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_initial_baseline_source_selections
            DROP CONSTRAINT IF EXISTS chk_hibss_lifecycle_status
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_initial_baseline_source_selections
            ADD CONSTRAINT chk_hibss_lifecycle_status
                CHECK (lifecycle_status IN ('ACTIVE', 'CONSUMED'))
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_initial_baseline_source_selections
            DROP CONSTRAINT IF EXISTS chk_hibss_consumed_consistency
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_initial_baseline_source_selections
            ADD CONSTRAINT chk_hibss_consumed_consistency
                CHECK (
                    (
                        lifecycle_status = 'ACTIVE'
                        AND consumed_at IS NULL
                        AND consumed_mrd_id IS NULL
                    )
                    OR (
                        lifecycle_status = 'CONSUMED'
                        AND consumed_at IS NOT NULL
                        AND consumed_mrd_id IS NOT NULL
                    )
                )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hibss_lifecycle_status
            ON public.hr_initial_baseline_source_selections (lifecycle_status, report_period)
        """
    )

    op.execute(
        """
        ALTER TABLE public.hr_initial_baseline_source_selections
            DROP CONSTRAINT IF EXISTS hr_initial_baseline_source_selections_source_batch_id_fkey
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_initial_baseline_source_selections
            ADD CONSTRAINT hr_initial_baseline_source_selections_source_batch_id_fkey
                FOREIGN KEY (source_batch_id)
                REFERENCES public.hr_import_batches (batch_id)
                ON DELETE RESTRICT
        """
    )

    op.execute(
        """
        ALTER TABLE public.hr_monthly_references
            ADD COLUMN IF NOT EXISTS source_batch_id BIGINT NULL
                REFERENCES public.hr_import_batches (batch_id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hmr_source_batch_id
            ON public.hr_monthly_references (source_batch_id)
            WHERE source_batch_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_hmr_source_batch_id")
    op.execute(
        """
        ALTER TABLE public.hr_monthly_references
            DROP COLUMN IF EXISTS source_batch_id
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_initial_baseline_source_selections
            DROP CONSTRAINT IF EXISTS hr_initial_baseline_source_selections_source_batch_id_fkey
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_initial_baseline_source_selections
            ADD CONSTRAINT hr_initial_baseline_source_selections_source_batch_id_fkey
                FOREIGN KEY (source_batch_id)
                REFERENCES public.hr_import_batches (batch_id)
                ON DELETE CASCADE
        """
    )
    op.execute("DROP INDEX IF EXISTS public.ix_hibss_lifecycle_status")
    op.execute(
        """
        ALTER TABLE public.hr_initial_baseline_source_selections
            DROP CONSTRAINT IF EXISTS chk_hibss_consumed_consistency
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_initial_baseline_source_selections
            DROP CONSTRAINT IF EXISTS chk_hibss_lifecycle_status
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_initial_baseline_source_selections
            DROP COLUMN IF EXISTS consumed_mrd_id,
            DROP COLUMN IF EXISTS consumed_at,
            DROP COLUMN IF EXISTS lifecycle_status
        """
    )
