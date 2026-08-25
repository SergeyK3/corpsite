"""Seed ordinary HR platform role and Oserova's personal enrollment grant.

This is deliberately a USER-targeted grant.  HR_reg remains a neutral
platform role and does not grant HR_ENROLLMENT_MANAGER to its other users.
"""
from __future__ import annotations

from alembic import op


revision = "p1q2r3s4t5u6"
down_revision = "o1p2q3r4s5t6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO public.roles (code, name, is_active)
        VALUES ('HR_reg', 'сотрудник1 ОК', TRUE)
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            is_active = TRUE
        """
    )
    op.execute(
        """
        UPDATE public.users u
        SET role_id = r.role_id
        FROM public.roles r
        WHERE lower(u.login) = 'oserova.aa'
          AND r.code = 'HR_reg'
          AND u.role_id IS DISTINCT FROM r.role_id
        """
    )
    op.execute(
        """
        INSERT INTO public.access_grants (
            access_role_id,
            target_type,
            target_id,
            resource_key,
            scope_type,
            scope_id,
            include_subtree,
            starts_at,
            ends_at,
            active_flag,
            granted_by_user_id,
            reason
        )
        SELECT
            ar.access_role_id,
            'USER',
            target.user_id,
            '*',
            'GLOBAL',
            NULL,
            FALSE,
            now(),
            NULL,
            TRUE,
            COALESCE(
                (
                    SELECT grantor.user_id
                    FROM public.users grantor
                    JOIN public.roles grantor_role ON grantor_role.role_id = grantor.role_id
                    WHERE grantor.is_active = TRUE
                      AND grantor_role.code = 'ADMIN'
                    ORDER BY grantor.user_id
                    LIMIT 1
                ),
                target.user_id
            ),
            'Seed: Oserova personal HR_ENROLLMENT_MANAGER grant'
        FROM public.access_roles ar
        JOIN public.users target ON lower(target.login) = 'oserova.aa'
        WHERE ar.code = 'HR_ENROLLMENT_MANAGER'
          AND ar.is_active = TRUE
          AND NOT EXISTS (
              SELECT 1
              FROM public.access_grants existing
              WHERE existing.access_role_id = ar.access_role_id
                AND existing.target_type = 'USER'
                AND existing.target_id = target.user_id
                AND existing.active_flag = TRUE
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM public.access_grants grant_row
        USING public.access_roles ar, public.users target
        WHERE grant_row.access_role_id = ar.access_role_id
          AND grant_row.target_type = 'USER'
          AND grant_row.target_id = target.user_id
          AND lower(target.login) = 'oserova.aa'
          AND ar.code = 'HR_ENROLLMENT_MANAGER'
          AND grant_row.reason = 'Seed: Oserova personal HR_ENROLLMENT_MANAGER grant'
        """
    )
