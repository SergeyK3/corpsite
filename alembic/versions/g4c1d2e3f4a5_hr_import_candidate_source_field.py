"""Add source_field to hr_import_document_candidates.

Revision ID: g4c1d2e3f4a5
Revises: f3a9b2c4d5e6
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op

revision = "g4c1d2e3f4a5"
down_revision = "f3a9b2c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.hr_import_document_candidates
            ADD COLUMN IF NOT EXISTS source_field TEXT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.hr_import_document_candidates
            DROP COLUMN IF EXISTS source_field
        """
    )
