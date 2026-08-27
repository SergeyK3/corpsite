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
            v_conflicts text;
        BEGIN
            SELECT string_agg(
                format('unit_id=%s, code=%s', unit_id, code),
                '; ' ORDER BY unit_id
            )
            INTO v_conflicts
            FROM public.org_units
            WHERE unit_id IN (79, 80, 81)
               OR code IN ('GENERAL', 'IT', 'TRANSFUSE');

            IF v_conflicts IS NOT NULL THEN
                RAISE EXCEPTION
                    'Cannot seed organizational units: unit_id or code is already occupied: %',
                    v_conflicts;
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM public.deps_group
                WHERE group_id = 2
            ) THEN
                RAISE EXCEPTION
                    'Cannot seed TRANSFUSE: expected paraclinical group_id=2 is missing';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM public.deps_group
                WHERE group_id = 3
            ) THEN
                RAISE EXCEPTION
                    'Cannot seed GENERAL and IT: expected administrative-household group_id=3 is missing';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM public.org_units
                WHERE unit_id = 41 AND is_active IS TRUE
            ) THEN
                RAISE EXCEPTION
                    'Cannot seed organizational units: active parent_unit_id=41 is missing';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        INSERT INTO public.org_units
            (unit_id, name, name_ru, code, parent_unit_id, group_id, is_active)
        VALUES
            (79, 'Общебольничный', NULL, 'GENERAL', 41, 3, TRUE),
            (80, 'IT бөлімі', NULL, 'IT', 41, 3, TRUE),
            (81, 'Трансфузиология', 'Трансфузиология', 'TRANSFUSE', 41, 2, TRUE);
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            v_sequence_name text;
        BEGIN
            v_sequence_name := pg_get_serial_sequence('public.org_units', 'unit_id');
            IF v_sequence_name IS NOT NULL THEN
                PERFORM setval(v_sequence_name::regclass, 81, TRUE);
            END IF;
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
        DELETE FROM public.org_units
        WHERE (unit_id = 79 AND name = 'Общебольничный' AND name_ru IS NULL
               AND code = 'GENERAL' AND parent_unit_id = 41 AND group_id = 3
               AND is_active IS TRUE)
           OR (unit_id = 80 AND name = 'IT бөлімі' AND name_ru IS NULL
               AND code = 'IT' AND parent_unit_id = 41 AND group_id = 3
               AND is_active IS TRUE)
           OR (unit_id = 81 AND name = 'Трансфузиология'
               AND (name_ru IS NULL OR name_ru = 'Трансфузиология')
               AND code = 'TRANSFUSE' AND parent_unit_id = 41 AND group_id = 2
               AND is_active IS TRUE);
        """
    )
