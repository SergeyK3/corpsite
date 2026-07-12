"""WP-PO-LC-DEL-005 — bind archive/restore permissions to HR_HEAD operational contour."""
from __future__ import annotations

from alembic import op

revision = "v6w7x8y9z0a1"
down_revision = "u5v6w7x8y9z0"
branch_labels = None
depends_on = None

_ARCHIVE_RESTORE_PERMISSIONS = (
    "PERSONNEL_ORDERS_ARCHIVE",
    "PERSONNEL_ORDERS_RESTORE",
)


def upgrade() -> None:
    for permission_code in _ARCHIVE_RESTORE_PERMISSIONS:
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
                COALESCE(
                    (
                        SELECT u.user_id
                        FROM public.users u
                        WHERE lower(u.login) = 'admin'
                          AND u.is_active = TRUE
                        ORDER BY u.user_id
                        LIMIT 1
                    ),
                    1
                ),
                'WP-PO-LC-DEL-005: HR head archive/restore permissions ({permission_code})'
            FROM public.access_roles ar
            CROSS JOIN public.roles r
            WHERE ar.code = '{permission_code}'
              AND r.code = 'HR_HEAD'
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
    for permission_code in _ARCHIVE_RESTORE_PERMISSIONS:
        op.execute(
            f"""
            DELETE FROM public.access_grants g
            USING public.access_roles ar, public.roles r
            WHERE g.access_role_id = ar.access_role_id
              AND g.target_type = 'ROLE'
              AND g.target_id = r.role_id
              AND ar.code = '{permission_code}'
              AND r.code = 'HR_HEAD'
              AND g.reason = 'WP-PO-LC-DEL-005: HR head archive/restore permissions ({permission_code})'
            """
        )
