"""ADR-053 Phase 2.6a — Permission Template binding schema (access_role_id + contour rules).

Engineering support only. Does not populate contour rules or template bindings.
Production binding completion is Phase 2.6b (ops; ADR-053 AC3 Pending).

Revision ID: m7n8o9p0q1r2
Revises: l6m7n8o9p0q1
"""
from __future__ import annotations

from alembic import op

revision = "m7n8o9p0q1r2"
down_revision = "l6m7n8o9p0q1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.permission_template
            ADD COLUMN IF NOT EXISTS access_role_id BIGINT NULL
                REFERENCES public.access_roles (access_role_id)
                ON DELETE SET NULL
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_permission_template_access_role_id
            ON public.permission_template (access_role_id)
            WHERE access_role_id IS NOT NULL
        """
    )

    op.execute(
        """
        COMMENT ON COLUMN public.permission_template.access_role_id IS
            'ADR-053: primary transitional Permission Template binding to access_roles (shadow/enforcement prep).'
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.permission_template_contour_rule (
            contour_rule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            client_scope_id BIGINT NOT NULL DEFAULT 1,
            org_unit_id BIGINT NOT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            catalog_position_id BIGINT NOT NULL
                REFERENCES public.positions (position_id) ON DELETE RESTRICT,
            access_role_id BIGINT NOT NULL
                REFERENCES public.access_roles (access_role_id) ON DELETE RESTRICT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            notes TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_ptcr_client_scope_positive
                CHECK (client_scope_id > 0),
            CONSTRAINT uq_ptcr_client_org_catalog
                UNIQUE (client_scope_id, org_unit_id, catalog_position_id)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ptcr_org_unit_catalog
            ON public.permission_template_contour_rule (org_unit_id, catalog_position_id)
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.permission_template_contour_rule IS
            'ADR-053 Phase 2.6a catalog (empty until Phase 2.6b): ops-approved position contour → access_role binding (position identity only).'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.permission_template_contour_rule CASCADE")
    op.execute(
        """
        ALTER TABLE public.permission_template
            DROP COLUMN IF EXISTS access_role_id
        """
    )
