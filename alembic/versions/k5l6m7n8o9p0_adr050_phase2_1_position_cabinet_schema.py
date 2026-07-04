"""ADR-050 Phase 2.1 — org-unique Position, Position Cabinet, Permission Template, legacy mapping.

Revision ID: k5l6m7n8o9p0
Revises: j9k0l1m2n3o4
"""
from __future__ import annotations

from alembic import op

revision = "k5l6m7n8o9p0"
down_revision = "j9k0l1m2n3o4"
branch_labels = None
depends_on = None

_LIFECYCLE_STATUSES = ("active", "vacant", "liquidated")


def upgrade() -> None:
    lifecycle_sql = ", ".join(f"'{s}'" for s in _LIFECYCLE_STATUSES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.org_unique_position (
            org_unique_position_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            client_scope_id BIGINT NOT NULL DEFAULT 1,
            org_unit_id BIGINT NOT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            catalog_position_id BIGINT NOT NULL
                REFERENCES public.positions (position_id) ON DELETE RESTRICT,
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_oup_client_scope_positive
                CHECK (client_scope_id > 0),
            CONSTRAINT chk_oup_lifecycle_status
                CHECK (lifecycle_status IN ({lifecycle_sql})),
            CONSTRAINT uq_oup_client_org_catalog
                UNIQUE (client_scope_id, org_unit_id, catalog_position_id)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oup_org_unit_id
            ON public.org_unique_position (org_unit_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oup_catalog_position_id
            ON public.org_unique_position (catalog_position_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oup_lifecycle_active
            ON public.org_unique_position (lifecycle_status)
            WHERE lifecycle_status = 'active'
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.org_unique_position IS
            'ADR-050: organization-unique staffing Position (org unit + catalog title reference).'
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.position_cabinet (
            position_cabinet_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            org_unique_position_id BIGINT NOT NULL
                REFERENCES public.org_unique_position (org_unique_position_id)
                ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_position_cabinet_org_unique_position
                UNIQUE (org_unique_position_id)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_position_cabinet_org_unique_position_id
            ON public.position_cabinet (org_unique_position_id)
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.position_cabinet IS
            'ADR-050: Position Cabinet — strict 1:1 with org_unique_position; owned by Position only.'
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.permission_template (
            permission_template_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            position_cabinet_id BIGINT NOT NULL
                REFERENCES public.position_cabinet (position_cabinet_id)
                ON DELETE RESTRICT,
            role_id BIGINT NULL
                REFERENCES public.roles (role_id) ON DELETE SET NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_permission_template_position_cabinet
                UNIQUE (position_cabinet_id)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_permission_template_position_cabinet_id
            ON public.permission_template (position_cabinet_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_permission_template_role_id
            ON public.permission_template (role_id)
            WHERE role_id IS NOT NULL
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.permission_template IS
            'ADR-050: Permission Template configuration inside Position Cabinet (not User/Person/Employment).'
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.legacy_position_mapping (
            legacy_position_mapping_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            client_scope_id BIGINT NOT NULL DEFAULT 1,
            org_unit_id BIGINT NOT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            catalog_position_id BIGINT NOT NULL
                REFERENCES public.positions (position_id) ON DELETE RESTRICT,
            org_unique_position_id BIGINT NOT NULL
                REFERENCES public.org_unique_position (org_unique_position_id)
                ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_lpm_client_scope_positive
                CHECK (client_scope_id > 0),
            CONSTRAINT uq_lpm_client_org_catalog
                UNIQUE (client_scope_id, org_unit_id, catalog_position_id),
            CONSTRAINT uq_lpm_org_unique_position
                UNIQUE (org_unique_position_id)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_lpm_org_unit_catalog
            ON public.legacy_position_mapping (org_unit_id, catalog_position_id)
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.legacy_position_mapping IS
            'ADR-050 Phase 2 transition: legacy (org_unit_id, catalog_position_id) to org_unique_position_id.'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.legacy_position_mapping CASCADE")
    op.execute("DROP TABLE IF EXISTS public.permission_template CASCADE")
    op.execute("DROP TABLE IF EXISTS public.position_cabinet CASCADE")
    op.execute("DROP TABLE IF EXISTS public.org_unique_position CASCADE")
