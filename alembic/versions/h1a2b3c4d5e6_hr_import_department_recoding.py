"""HR Import Phase 2F — department_recoding lookup table.

Revision ID: h1a2b3c4d5e6
Revises: g4c1d2e3f4a5
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op

revision = "h1a2b3c4d5e6"
down_revision = "g4c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.department_recoding (
            id BIGSERIAL PRIMARY KEY,
            import_department_name TEXT NOT NULL,
            org_unit_id BIGINT NULL REFERENCES public.org_units(unit_id) ON DELETE SET NULL,
            org_unit_name TEXT NOT NULL DEFAULT '',
            department_group TEXT NOT NULL DEFAULT 'CLINICAL',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT department_recoding_group_check CHECK (
                department_group IN ('CLINICAL', 'PARACLINICAL', 'ADMINISTRATIVE')
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_department_recoding_import_name
            ON public.department_recoding (LOWER(TRIM(import_department_name)))
            WHERE is_active = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_department_recoding_org_unit_id
            ON public.department_recoding (org_unit_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.department_recoding CASCADE")
