"""PPR additional profile JSON on personnel_record_metadata."""
from __future__ import annotations

from alembic import op

revision = "n5o6p7q8r9s0"
down_revision = "m4n5o6p7q8r9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.personnel_record_metadata
            ADD COLUMN IF NOT EXISTS additional_profile JSONB NULL
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.personnel_record_metadata.additional_profile IS
            'Canonical PPR additional profile: languages, awards, academic degrees/titles.'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.personnel_record_metadata
            DROP COLUMN IF EXISTS additional_profile
        """
    )
