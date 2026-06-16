"""hr import phase 2b match not processed

Revision ID: d3e4f5a6b7c8
Revises: c1a8f92e4b03
Create Date: 2026-06-16 20:00:00.000000

ADR-038 Phase 2B: allow NOT_PROCESSED match_status before match engine runs.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c1a8f92e4b03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.hr_import_rows
            DROP CONSTRAINT IF EXISTS chk_hr_import_rows_match_status
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_import_rows
            ADD CONSTRAINT chk_hr_import_rows_match_status
                CHECK (match_status IN (
                    'NOT_PROCESSED',
                    'AUTO_MATCH', 'REVIEW_REQUIRED', 'NO_MATCH', 'INVALID_DATA', 'SKIPPED'
                ))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE public.hr_import_rows
        SET match_status = 'REVIEW_REQUIRED'
        WHERE match_status = 'NOT_PROCESSED'
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_import_rows
            DROP CONSTRAINT IF EXISTS chk_hr_import_rows_match_status
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_import_rows
            ADD CONSTRAINT chk_hr_import_rows_match_status
                CHECK (match_status IN (
                    'AUTO_MATCH', 'REVIEW_REQUIRED', 'NO_MATCH', 'INVALID_DATA', 'SKIPPED'
                ))
        """
    )
