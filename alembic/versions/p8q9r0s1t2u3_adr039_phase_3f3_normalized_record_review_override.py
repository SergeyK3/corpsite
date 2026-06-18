"""ADR-039 Phase 3F.3 — normalized record review override layer.

Revision ID: p8q9r0s1t2u3
Revises: o7p8q9r0s1t2
"""
from __future__ import annotations

from alembic import op

revision = "p8q9r0s1t2u3"
down_revision = "o7p8q9r0s1t2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.hr_import_normalized_records
            ADD COLUMN IF NOT EXISTS review_override_json JSONB NULL,
            ADD COLUMN IF NOT EXISTS review_override_updated_by BIGINT NULL,
            ADD COLUMN IF NOT EXISTS review_override_updated_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_hinr_review_override_updated_by'
            ) THEN
                ALTER TABLE public.hr_import_normalized_records
                    ADD CONSTRAINT fk_hinr_review_override_updated_by
                        FOREIGN KEY (review_override_updated_by)
                        REFERENCES public.users (user_id);
            END IF;
        END $$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.hr_import_normalized_records
            DROP CONSTRAINT IF EXISTS fk_hinr_review_override_updated_by
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_import_normalized_records
            DROP COLUMN IF EXISTS review_override_updated_at,
            DROP COLUMN IF EXISTS review_override_updated_by,
            DROP COLUMN IF EXISTS review_override_json
        """
    )
