"""Add optional Kazakh org-unit name and document-form fields.

Revision ID: orgkk001
Revises: pojson019
"""
from __future__ import annotations

from alembic import op


revision = "orgkk001"
down_revision = "pojson019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No backfill belongs in this schema migration.  Reference data is loaded
    # separately by scripts/sync_org_units_name_kk.py after review.
    op.execute("ALTER TABLE public.org_units ADD COLUMN IF NOT EXISTS name_kk TEXT NULL")
    op.execute("ALTER TABLE public.org_units ADD COLUMN IF NOT EXISTS document_genitive_kk TEXT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE public.org_units DROP COLUMN IF EXISTS document_genitive_kk")
    op.execute("ALTER TABLE public.org_units DROP COLUMN IF EXISTS name_kk")
