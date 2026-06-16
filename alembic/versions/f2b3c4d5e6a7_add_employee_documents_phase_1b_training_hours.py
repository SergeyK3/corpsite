"""add employee documents phase 1b training hours

Revision ID: f2b3c4d5e6a7
Revises: d9e8f71a2b05
Create Date: 2026-06-16 14:00:00.000000

ADR-037 Phase 1B: hours column, tracks_hours seed, aggregation index.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f2b3c4d5e6a7"
down_revision: Union[str, Sequence[str], None] = "d9e8f71a2b05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.employee_documents
            ADD COLUMN IF NOT EXISTS hours INTEGER NULL
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'chk_employee_documents_hours_nonneg'
            ) THEN
                ALTER TABLE public.employee_documents
                    ADD CONSTRAINT chk_employee_documents_hours_nonneg
                    CHECK (hours IS NULL OR hours >= 0);
            END IF;
        END $$
        """
    )

    op.execute(
        """
        UPDATE public.document_types
        SET tracks_hours = TRUE
        WHERE code IN (
            'CONTINUING_EDUCATION',
            'CONFERENCE_PARTICIPATION',
            'MASTERCLASS_PARTICIPATION',
            'SEMINAR_PARTICIPATION'
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_employee_documents_training_hours
        ON public.employee_documents (employee_id, issued_at DESC)
        WHERE lifecycle_status = 'ACTIVE'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_employee_documents_training_hours")

    op.execute(
        """
        UPDATE public.document_types
        SET tracks_hours = FALSE
        WHERE code IN (
            'CONTINUING_EDUCATION',
            'CONFERENCE_PARTICIPATION',
            'MASTERCLASS_PARTICIPATION',
            'SEMINAR_PARTICIPATION'
        )
        """
    )

    op.execute(
        """
        ALTER TABLE public.employee_documents
            DROP CONSTRAINT IF EXISTS chk_employee_documents_hours_nonneg
        """
    )

    op.execute(
        """
        ALTER TABLE public.employee_documents
            DROP COLUMN IF EXISTS hours
        """
    )
