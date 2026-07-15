"""ADR-046 F1 — org_unit_allowed_positions schema (allowed positions foundation).

Engineering schema only. Does not seed HR pilot links or mutate employees.

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
"""
from __future__ import annotations

from alembic import op

revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.org_unit_allowed_positions (
            org_unit_allowed_position_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            org_unit_id BIGINT NOT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            position_id BIGINT NOT NULL
                REFERENCES public.positions (position_id) ON DELETE RESTRICT,
            sort_order INTEGER NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_ouap_org_unit_position
                UNIQUE (org_unit_id, position_id)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ouap_org_unit_id
            ON public.org_unit_allowed_positions (org_unit_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ouap_position_id
            ON public.org_unit_allowed_positions (position_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ouap_org_unit_sort
            ON public.org_unit_allowed_positions (org_unit_id, sort_order, org_unit_allowed_position_id)
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.org_unit_allowed_positions IS
            'ADR-046 F1: official positions allowed for an org unit (staffing list; not headcount).'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.org_unit_allowed_positions CASCADE")
