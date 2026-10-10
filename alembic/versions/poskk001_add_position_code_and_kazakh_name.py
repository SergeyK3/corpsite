"""Add an optional Kazakh name to positions.

Revision ID: poskk001
Revises: orgkk001
"""
from __future__ import annotations

from alembic import op


revision = "poskk001"
down_revision = "orgkk001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.positions ADD COLUMN IF NOT EXISTS name_kk TEXT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE public.positions DROP COLUMN IF EXISTS name_kk")
