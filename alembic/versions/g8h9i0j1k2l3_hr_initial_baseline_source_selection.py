"""Persist selected import batch per report period for initial baseline formation.

Revision ID: g8h9i0j1k2l3
Revises: f7a8b9c0d1e2
"""
from __future__ import annotations

from alembic import op

revision = "g8h9i0j1k2l3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_initial_baseline_source_selections (
            report_period DATE NOT NULL PRIMARY KEY,
            source_batch_id BIGINT NOT NULL
                REFERENCES public.hr_import_batches (batch_id) ON DELETE CASCADE,
            selected_by BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            selected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT chk_hibss_report_period_month_start
                CHECK (report_period = date_trunc('month', report_period)::date)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hibss_source_batch_id
            ON public.hr_initial_baseline_source_selections (source_batch_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.hr_initial_baseline_source_selections")
