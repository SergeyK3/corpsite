"""WP-CL-002: register the control-list bulk-export permission."""
from __future__ import annotations

from alembic import op

revision = "w6x7y8z9a0b1"
down_revision = "v5w6x7y8z9a"
branch_labels = None
depends_on = None

_PERMISSION_CODE = "CONTROL_LIST_EXPORT"
_ROLE_CODE = "HR_HEAD"
_GRANT_REASON = "WP-CL-002: control-list export for HR_HEAD"


def upgrade() -> None:
    op.execute(
        f"""
        DO $migration$
        DECLARE
            v_role_id BIGINT;
            v_role_count INTEGER;
            v_access_role_id BIGINT;
            v_granted_by_user_id BIGINT;
        BEGIN
            IF EXISTS (
                SELECT 1
                  FROM public.access_roles
                 WHERE code = '{_PERMISSION_CODE}'
            ) THEN
                RAISE EXCEPTION
                    'w6x7y8z9a0b1 cannot create permission %: code already exists',
                    '{_PERMISSION_CODE}';
            END IF;

            SELECT COUNT(*), MIN(role_id)
              INTO v_role_count, v_role_id
              FROM public.roles
             WHERE code = '{_ROLE_CODE}';

            IF v_role_count <> 1 THEN
                RAISE EXCEPTION
                    'w6x7y8z9a0b1 requires exactly one role %, found %',
                    '{_ROLE_CODE}', v_role_count;
            END IF;

            SELECT user_id
              INTO v_granted_by_user_id
              FROM public.users
             WHERE is_active = TRUE
             ORDER BY CASE WHEN lower(login) = 'admin' THEN 0 ELSE 1 END, user_id
             LIMIT 1;

            IF v_granted_by_user_id IS NULL THEN
                RAISE EXCEPTION
                    'w6x7y8z9a0b1 requires an active user for granted_by_user_id';
            END IF;

            INSERT INTO public.access_roles (
                code, name, description, access_level, level_rank, is_system
            ) VALUES (
                '{_PERMISSION_CODE}',
                'Control List Export',
                'Build and export the scoped personnel control list with personal data',
                'MANAGER', 20, TRUE
            )
            RETURNING access_role_id INTO v_access_role_id;

            INSERT INTO public.access_grants (
                access_role_id,
                target_type,
                target_id,
                granted_by_user_id,
                reason
            ) VALUES (
                v_access_role_id,
                'ROLE',
                v_role_id,
                v_granted_by_user_id,
                '{_GRANT_REASON}'
            );
        END
        $migration$;
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM public.access_grants g
        USING public.access_roles ar, public.roles r
        WHERE g.access_role_id = ar.access_role_id
          AND g.target_type = 'ROLE'
          AND g.target_id = r.role_id
          AND ar.code = '{_PERMISSION_CODE}'
          AND r.code = '{_ROLE_CODE}'
          AND g.reason = '{_GRANT_REASON}'
        """
    )
    op.execute(
        f"""
        DELETE FROM public.access_roles ar
        WHERE ar.code = '{_PERMISSION_CODE}'
          AND NOT EXISTS (
              SELECT 1
                FROM public.access_grants g
               WHERE g.access_role_id = ar.access_role_id
          )
        """
    )
