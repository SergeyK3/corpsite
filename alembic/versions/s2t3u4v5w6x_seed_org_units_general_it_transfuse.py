"""seed GENERAL, IT and TRANSFUSE organizational units

Revision ID: s2t3u4v5w6x
Revises: r1s2t3u4v5w6
"""
from alembic import op


revision = "s2t3u4v5w6x"
down_revision = "r1s2t3u4v5w6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            v_parent_unit_id bigint;
            v_disp_count integer;
            v_conflicts text;
        BEGIN
            SELECT COUNT(*), MIN(parent_unit_id)
            INTO v_disp_count, v_parent_unit_id
            FROM public.org_units
            WHERE code = 'DISP'
              AND is_active IS TRUE;

            IF v_disp_count <> 1 OR v_parent_unit_id IS NULL THEN
                RAISE EXCEPTION
                    'Cannot seed organizational units: expected one active DISP with a parent, found %',
                    v_disp_count;
            END IF;

            SELECT string_agg(
                format('unit_id=%s, code=%s', unit_id, code),
                '; ' ORDER BY unit_id
            )
            INTO v_conflicts
            FROM public.org_units
            WHERE code IN ('GENERAL', 'IT', 'TRANSFUSE');

            IF v_conflicts IS NOT NULL THEN
                RAISE EXCEPTION
                    'Cannot seed organizational units: target code is already occupied: %',
                    v_conflicts;
            END IF;

            INSERT INTO public.org_units
                (name, code, parent_unit_id, group_id, is_active)
            VALUES
                ('Общебольничный', 'GENERAL', v_parent_unit_id, 3, TRUE),
                ('IT бөлімі', 'IT', v_parent_unit_id, 3, TRUE),
                ('Трансфузиология', 'TRANSFUSE', v_parent_unit_id, 2, TRUE);
        END
        $$;
        """
    )


def downgrade() -> None:
    # Do not cascade or change dependent data.  If a later change made one of
    # these units referenced, the database rejects this delete rather than
    # deleting or altering related records.
    op.execute(
        """
        DELETE FROM public.org_units target
        USING public.org_units dispensary
        WHERE dispensary.code = 'DISP'
          AND dispensary.is_active IS TRUE
          AND dispensary.parent_unit_id IS NOT NULL
          AND target.parent_unit_id = dispensary.parent_unit_id
          AND target.is_active IS TRUE
          AND (
              (target.name = 'Общебольничный' AND target.code = 'GENERAL' AND target.group_id = 3)
              OR (target.name = 'IT бөлімі' AND target.code = 'IT' AND target.group_id = 3)
              OR (target.name = 'Трансфузиология' AND target.code = 'TRANSFUSE' AND target.group_id = 2)
          )
        """
    )
