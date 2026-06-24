"""Add archived_at to regular_tasks for template lifecycle.

Revision ID: j9k0l1m2n3o4
Revises: i8j9k0l1m2n3
"""
from __future__ import annotations

from alembic import op

revision = "j9k0l1m2n3o4"
down_revision = "i8j9k0l1m2n3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.regular_tasks
          ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.regular_tasks
          DROP COLUMN IF EXISTS archived_at;
        """
    )
