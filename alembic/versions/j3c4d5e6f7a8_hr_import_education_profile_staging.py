"""HR import Phase 2F.3 — education profile staging overrides.

Revision ID: j3c4d5e6f7a8
Revises: i2b3c4d5e6f7
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op

revision = "j3c4d5e6f7a8"
down_revision = "i2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.hr_import_rows
            ADD COLUMN IF NOT EXISTS profile_override JSONB NULL,
            ADD COLUMN IF NOT EXISTS profile_status TEXT NOT NULL DEFAULT 'active',
            ADD COLUMN IF NOT EXISTS profile_review_status TEXT NOT NULL DEFAULT 'pending'
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_hr_import_rows_profile_status'
            ) THEN
                ALTER TABLE public.hr_import_rows
                    ADD CONSTRAINT ck_hr_import_rows_profile_status
                    CHECK (profile_status IN ('active', 'archived'));
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_hr_import_rows_profile_review_status'
            ) THEN
                ALTER TABLE public.hr_import_rows
                    ADD CONSTRAINT ck_hr_import_rows_profile_review_status
                    CHECK (profile_review_status IN ('pending', 'reviewed', 'needs_attention'));
            END IF;
        END $$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.hr_import_rows
            DROP COLUMN IF EXISTS profile_override,
            DROP COLUMN IF EXISTS profile_status,
            DROP COLUMN IF EXISTS profile_review_status
        """
    )
