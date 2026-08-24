"""Grant HR_HEAD minimal read-only access to Incoming Information."""
from __future__ import annotations

from alembic import op

revision = "g4b5c6d7e8f9"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None

_PERMISSION_CODE = "INCOMING_INFO_READ"
_ROLE_ID = 14
_ROLE_CODE = "HR_HEAD"
_GRANT_REASON = "HR_HEAD: read-only access to Incoming Information"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO public.access_grants (
            access_role_id,
            target_type,
            target_id,
            granted_by_user_id,
            reason
        )
        SELECT
            ar.access_role_id,
            'ROLE',
            r.role_id,
            u.user_id,
            '{_GRANT_REASON}'
        FROM public.access_roles ar
        CROSS JOIN public.roles r
        CROSS JOIN LATERAL (
            SELECT u.user_id
            FROM public.users u
            WHERE lower(u.login) = 'admin'
              AND u.is_active = TRUE
            ORDER BY u.user_id
            LIMIT 1
        ) u
        WHERE ar.code = '{_PERMISSION_CODE}'
          AND ar.is_active = TRUE
          AND r.role_id = {_ROLE_ID}
          AND r.code = '{_ROLE_CODE}'
          AND NOT EXISTS (
              SELECT 1
              FROM public.access_grants g
              WHERE g.active_flag = TRUE
                AND g.access_role_id = ar.access_role_id
                AND g.target_type = 'ROLE'
                AND g.target_id = r.role_id
          )
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
          AND r.role_id = {_ROLE_ID}
          AND r.code = '{_ROLE_CODE}'
          AND g.reason = '{_GRANT_REASON}'
        """
    )
