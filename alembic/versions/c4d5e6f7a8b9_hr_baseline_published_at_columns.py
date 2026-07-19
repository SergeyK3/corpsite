"""Rename baseline promoted_* columns to published_* (ADR-045).

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
"""
from __future__ import annotations

from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'hr_control_list_baselines'
                  AND column_name = 'promoted_at'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'hr_control_list_baselines'
                  AND column_name = 'published_at'
            ) THEN
                ALTER TABLE public.hr_control_list_baselines
                    RENAME COLUMN promoted_at TO published_at;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'hr_control_list_baselines'
                  AND column_name = 'promoted_by'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'hr_control_list_baselines'
                  AND column_name = 'published_by'
            ) THEN
                ALTER TABLE public.hr_control_list_baselines
                    RENAME COLUMN promoted_by TO published_by;
            END IF;
        END $$
        """
    )
    op.execute("DROP INDEX IF EXISTS public.ix_hclb_report_period_promoted_at")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hclb_report_period_published_at
            ON public.hr_control_list_baselines (report_period, published_at DESC)
            WHERE deleted_at IS NULL
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW public.hr_canonical_snapshots AS
        SELECT
            bl.baseline_id AS snapshot_id,
            bl.source_batch_id,
            bl.source_type,
            bl.entry_count,
            bl.published_by AS promoted_by,
            bl.published_at AS promoted_at,
            bl.publication_origin_id,
            bl.report_period,
            bl.deleted_at
        FROM public.hr_control_list_baselines bl
        WHERE bl.deleted_at IS NULL
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.hr_control_list_baselines IS
            'Approved control-list baseline. Effective per period = MAX(published_at) where deleted_at IS NULL.';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'hr_control_list_baselines'
                  AND column_name = 'published_at'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'hr_control_list_baselines'
                  AND column_name = 'promoted_at'
            ) THEN
                ALTER TABLE public.hr_control_list_baselines
                    RENAME COLUMN published_at TO promoted_at;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'hr_control_list_baselines'
                  AND column_name = 'published_by'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'hr_control_list_baselines'
                  AND column_name = 'promoted_by'
            ) THEN
                ALTER TABLE public.hr_control_list_baselines
                    RENAME COLUMN published_by TO promoted_by;
            END IF;
        END $$
        """
    )
    op.execute("DROP INDEX IF EXISTS public.ix_hclb_report_period_published_at")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hclb_report_period_promoted_at
            ON public.hr_control_list_baselines (report_period, promoted_at DESC)
            WHERE deleted_at IS NULL
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW public.hr_canonical_snapshots AS
        SELECT
            bl.baseline_id AS snapshot_id,
            bl.source_batch_id,
            bl.source_type,
            bl.entry_count,
            bl.promoted_by,
            bl.promoted_at,
            bl.publication_origin_id,
            bl.report_period,
            bl.deleted_at
        FROM public.hr_control_list_baselines bl
        WHERE bl.deleted_at IS NULL
        """
    )
