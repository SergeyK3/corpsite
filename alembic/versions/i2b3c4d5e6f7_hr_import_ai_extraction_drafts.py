"""HR import Phase 2F.2 — AI extraction drafts for review staging.

Revision ID: i2b3c4d5e6f7
Revises: h1a2b3c4d5e6
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op

revision = "i2b3c4d5e6f7"
down_revision = "h1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_import_ai_extraction_drafts (
            draft_id BIGSERIAL PRIMARY KEY,
            batch_id BIGINT NOT NULL,
            row_id BIGINT NOT NULL,
            parse_method TEXT NOT NULL DEFAULT 'llm_assisted',
            status TEXT NOT NULL DEFAULT 'draft',
            extraction JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_hr_import_ai_drafts_batch
                FOREIGN KEY (batch_id)
                REFERENCES public.hr_import_batches(batch_id)
                ON DELETE CASCADE,
            CONSTRAINT fk_hr_import_ai_drafts_row
                FOREIGN KEY (row_id)
                REFERENCES public.hr_import_rows(row_id)
                ON DELETE CASCADE,
            CONSTRAINT uq_hr_import_ai_drafts_row UNIQUE (row_id),
            CONSTRAINT ck_hr_import_ai_drafts_status
                CHECK (status IN ('draft', 'confirmed'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_ai_drafts_batch
            ON public.hr_import_ai_extraction_drafts (batch_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.hr_import_ai_extraction_drafts")
