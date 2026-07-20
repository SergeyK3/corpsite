"""personnel intake link token ciphertext for HR recovery

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
Create Date: 2026-07-20
"""
from __future__ import annotations

from alembic import op

revision = "j1k2l3m4n5o6"
down_revision = "i0j1k2l3m4n5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.personnel_intake_links
        ADD COLUMN IF NOT EXISTS token_ciphertext TEXT NULL
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.personnel_intake_links.token_ciphertext IS
        'Fernet-encrypted raw intake bearer token for HR recovery; NULL for legacy hash-only links.'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.personnel_intake_links
        DROP COLUMN IF EXISTS token_ciphertext
        """
    )
