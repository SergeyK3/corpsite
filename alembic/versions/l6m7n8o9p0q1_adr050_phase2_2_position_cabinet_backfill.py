"""ADR-050 Phase 2.2 — idempotent backfill legacy staffing pairs → Position + Cabinet + Template + mapping.

Revision ID: l6m7n8o9p0q1
Revises: k5l6m7n8o9p0
"""
from __future__ import annotations

from alembic import op

revision = "l6m7n8o9p0q1"
down_revision = "k5l6m7n8o9p0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            rec RECORD;
            v_oup_id BIGINT;
            v_pc_id BIGINT;
            v_pair_count INT := 0;
        BEGIN
            FOR rec IN
                SELECT DISTINCT
                    1 AS client_scope_id,
                    pairs.org_unit_id,
                    pairs.catalog_position_id
                FROM (
                    SELECT e.org_unit_id, e.position_id AS catalog_position_id
                    FROM public.employees e
                    WHERE e.org_unit_id IS NOT NULL
                      AND e.position_id IS NOT NULL
                    UNION
                    SELECT pa.org_unit_id, pa.position_id AS catalog_position_id
                    FROM public.person_assignments pa
                    WHERE pa.org_unit_id IS NOT NULL
                      AND pa.position_id IS NOT NULL
                ) pairs
                INNER JOIN public.org_units ou
                    ON ou.unit_id = pairs.org_unit_id
                INNER JOIN public.positions pos
                    ON pos.position_id = pairs.catalog_position_id
                ORDER BY pairs.org_unit_id, pairs.catalog_position_id
            LOOP
                IF EXISTS (
                    SELECT 1
                    FROM public.legacy_position_mapping lpm
                    WHERE lpm.client_scope_id = rec.client_scope_id
                      AND lpm.org_unit_id = rec.org_unit_id
                      AND lpm.catalog_position_id = rec.catalog_position_id
                ) THEN
                    CONTINUE;
                END IF;

                INSERT INTO public.org_unique_position (
                    client_scope_id,
                    org_unit_id,
                    catalog_position_id
                )
                VALUES (
                    rec.client_scope_id,
                    rec.org_unit_id,
                    rec.catalog_position_id
                )
                ON CONFLICT ON CONSTRAINT uq_oup_client_org_catalog
                DO UPDATE SET updated_at = now()
                RETURNING org_unique_position_id INTO v_oup_id;

                INSERT INTO public.position_cabinet (org_unique_position_id)
                VALUES (v_oup_id)
                ON CONFLICT ON CONSTRAINT uq_position_cabinet_org_unique_position
                DO NOTHING;

                SELECT pc.position_cabinet_id INTO v_pc_id
                FROM public.position_cabinet pc
                WHERE pc.org_unique_position_id = v_oup_id;

                INSERT INTO public.permission_template (
                    position_cabinet_id,
                    role_id,
                    is_active
                )
                VALUES (v_pc_id, NULL, TRUE)
                ON CONFLICT ON CONSTRAINT uq_permission_template_position_cabinet
                DO NOTHING;

                INSERT INTO public.legacy_position_mapping (
                    client_scope_id,
                    org_unit_id,
                    catalog_position_id,
                    org_unique_position_id
                )
                VALUES (
                    rec.client_scope_id,
                    rec.org_unit_id,
                    rec.catalog_position_id,
                    v_oup_id
                )
                ON CONFLICT ON CONSTRAINT uq_lpm_client_org_catalog
                DO NOTHING;

                v_pair_count := v_pair_count + 1;
            END LOOP;

            RAISE NOTICE 'ADR-050 Phase 2.2: backfilled % legacy staffing pairs', v_pair_count;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM public.legacy_position_mapping")
    op.execute("DELETE FROM public.permission_template")
    op.execute("DELETE FROM public.position_cabinet")
    op.execute("DELETE FROM public.org_unique_position")
