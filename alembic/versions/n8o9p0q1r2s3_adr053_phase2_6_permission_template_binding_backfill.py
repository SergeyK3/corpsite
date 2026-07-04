"""ADR-053 Phase 2.6a — apply position-contour rules to permission_template.access_role_id.

Idempotent backfill mechanism only. No-op when permission_template_contour_rule is empty.
Re-run after Phase 2.6b ops inserts approved contour rules (see OPS-030).

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
"""
from __future__ import annotations

from alembic import op

revision = "n8o9p0q1r2s3"
down_revision = "m7n8o9p0q1r2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'permission_template'
                  AND column_name = 'access_role_id'
            ) THEN
                RAISE EXCEPTION 'ADR-053 Phase 2.6a: permission_template.access_role_id missing — run m7n8o9p0q1r2 first';
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        UPDATE public.permission_template pt
        SET
            access_role_id = cr.access_role_id,
            updated_at = now()
        FROM public.position_cabinet pc
        JOIN public.org_unique_position oup
          ON oup.org_unique_position_id = pc.org_unique_position_id
        JOIN public.permission_template_contour_rule cr
          ON cr.client_scope_id = oup.client_scope_id
         AND cr.org_unit_id = oup.org_unit_id
         AND cr.catalog_position_id = oup.catalog_position_id
         AND cr.is_active = TRUE
        JOIN public.access_roles ar
          ON ar.access_role_id = cr.access_role_id
         AND ar.is_active = TRUE
        WHERE pt.position_cabinet_id = pc.position_cabinet_id
          AND pt.access_role_id IS DISTINCT FROM cr.access_role_id
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE public.permission_template
        SET access_role_id = NULL,
            updated_at = now()
        WHERE access_role_id IS NOT NULL
        """
    )
