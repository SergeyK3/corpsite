"""Allow education document_kind on hr_import_document_candidates.

Revision ID: f3a9b2c4d5e6
Revises: e2c4f8a1b3d5
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op

revision = "f3a9b2c4d5e6"
down_revision = "e2c4f8a1b3d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.hr_import_document_candidates
            DROP CONSTRAINT IF EXISTS chk_hr_import_document_candidates_kind
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_import_document_candidates
            ADD CONSTRAINT chk_hr_import_document_candidates_kind
            CHECK (document_kind IN ('training', 'certification', 'education'))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.hr_import_document_candidates
            DROP CONSTRAINT IF EXISTS chk_hr_import_document_candidates_kind
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_import_document_candidates
            ADD CONSTRAINT chk_hr_import_document_candidates_kind
            CHECK (document_kind IN ('training', 'certification'))
        """
    )
