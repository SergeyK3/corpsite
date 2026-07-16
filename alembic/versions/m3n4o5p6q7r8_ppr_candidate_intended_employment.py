"""PPR candidate intended employment columns on personnel_record_metadata.

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
"""
from __future__ import annotations

from alembic import op

revision = "m3n4o5p6q7r8"
down_revision = "l2m3n4o5p6q7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.personnel_record_metadata
            ADD COLUMN IF NOT EXISTS intended_org_group_id BIGINT NULL,
            ADD COLUMN IF NOT EXISTS intended_org_unit_id BIGINT NULL,
            ADD COLUMN IF NOT EXISTS intended_position_id BIGINT NULL,
            ADD COLUMN IF NOT EXISTS intended_employment_rate NUMERIC(4,2) NULL
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.personnel_record_metadata.intended_org_group_id IS
            'HR intent: department group for planned hire (not Employment).'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.personnel_record_metadata.intended_org_unit_id IS
            'HR intent: org unit for planned hire (not Employment).'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.personnel_record_metadata.intended_position_id IS
            'HR intent: position for planned hire (not Employment).'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.personnel_record_metadata.intended_employment_rate IS
            'HR intent: employment rate for planned hire (not Employment).'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.personnel_record_metadata
            DROP COLUMN IF EXISTS intended_employment_rate,
            DROP COLUMN IF EXISTS intended_position_id,
            DROP COLUMN IF EXISTS intended_org_unit_id,
            DROP COLUMN IF EXISTS intended_org_group_id
        """
    )
