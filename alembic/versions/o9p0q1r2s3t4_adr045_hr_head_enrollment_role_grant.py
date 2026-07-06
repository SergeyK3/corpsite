"""ADR-045 — HR_HEAD directory role gets HR_ENROLLMENT_MANAGER via ROLE grant.

Mirrors production DEP_ADMIN pattern (ADR-042): operational HR contour follows
public.roles.code, not per-user grants.
"""
from __future__ import annotations

from alembic import op

revision = "o9p0q1r2s3t4"
down_revision = "n8o9p0q1r2s3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
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
            'ADR-045: HR head operational contour (HR_ENROLLMENT_MANAGER via HR_HEAD role)'
        FROM public.access_roles ar
        CROSS JOIN public.roles r
        WHERE ar.code = 'HR_ENROLLMENT_MANAGER'
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
    op.execute(
        """
        DELETE FROM public.access_grants g
        USING public.access_roles ar, public.roles r
        WHERE g.access_role_id = ar.access_role_id
          AND g.target_type = 'ROLE'
          AND g.target_id = r.role_id
          AND ar.code = 'HR_ENROLLMENT_MANAGER'
          AND r.code = 'HR_HEAD'
          AND g.reason = 'ADR-045: HR head operational contour (HR_ENROLLMENT_MANAGER via HR_HEAD role)'
        """
    )
