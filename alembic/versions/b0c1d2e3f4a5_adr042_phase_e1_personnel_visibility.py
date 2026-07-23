"""ADR-042 Phase E1 — personnel visibility scope assignments.

Revision ID: b0c1d2e3f4a5
Revises: a0b1c2d3e4f6
"""
from __future__ import annotations

from alembic import op

revision = "b0c1d2e3f4a5"
down_revision = "a0b1c2d3e4f6"
branch_labels = None
depends_on = None

_TARGET_TYPES = ("USER", "POSITION", "DEPARTMENT")
_SCOPE_TYPES = ("ORGANIZATION", "DEPARTMENT", "DEPARTMENT_GROUP")

_SAL_EVENT_TYPES = (
    "LOGIN_SUCCESS",
    "LOGIN_FAILED",
    "LOGOUT",
    "PASSWORD_RESET_REQUESTED",
    "PASSWORD_RESET_COMPLETED",
    "PASSWORD_CHANGED",
    "TEMP_PASSWORD_ISSUED",
    "USER_LOCKED",
    "USER_UNLOCKED",
    "ACCESS_GRANTED",
    "ACCESS_REVOKED",
    "ACCESS_CHANGED",
    "ENROLLMENT_APPROVED",
    "ENROLLMENT_REJECTED",
    "ENROLLMENT_COMPLETED",
    "USER_BLOCKED",
    "USER_UNBLOCKED",
    "PERSON_IIN_RECONCILED",
    "VISIBILITY_GRANTED",
    "VISIBILITY_REVOKED",
)


def upgrade() -> None:
    target_types_sql = ", ".join(f"'{t}'" for t in _TARGET_TYPES)
    scope_types_sql = ", ".join(f"'{t}'" for t in _SCOPE_TYPES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.personnel_visibility_assignments (
            assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            target_type TEXT NOT NULL,
            target_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE CASCADE,
            target_position_id BIGINT NULL
                REFERENCES public.positions (position_id) ON DELETE CASCADE,
            target_department_id BIGINT NULL
                REFERENCES public.org_units (unit_id) ON DELETE CASCADE,
            scope_type TEXT NOT NULL,
            scope_department_id BIGINT NULL
                REFERENCES public.org_units (unit_id) ON DELETE SET NULL,
            scope_department_group_id BIGINT NULL
                REFERENCES public.deps_group (group_id) ON DELETE SET NULL,
            can_view_personnel BOOLEAN NOT NULL DEFAULT TRUE,
            can_view_tasks BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            revoked_at TIMESTAMPTZ NULL,
            revoked_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            revoke_reason TEXT NULL,
            CONSTRAINT chk_pva_target_type
                CHECK (target_type IN ({target_types_sql})),
            CONSTRAINT chk_pva_scope_type
                CHECK (scope_type IN ({scope_types_sql})),
            CONSTRAINT chk_pva_target_ref
                CHECK (
                    (target_type = 'USER' AND target_user_id IS NOT NULL
                        AND target_position_id IS NULL AND target_department_id IS NULL)
                    OR (target_type = 'POSITION' AND target_position_id IS NOT NULL
                        AND target_user_id IS NULL AND target_department_id IS NULL)
                    OR (target_type = 'DEPARTMENT' AND target_department_id IS NOT NULL
                        AND target_user_id IS NULL AND target_position_id IS NULL)
                ),
            CONSTRAINT chk_pva_scope_ref
                CHECK (
                    (scope_type = 'ORGANIZATION'
                        AND scope_department_id IS NULL AND scope_department_group_id IS NULL)
                    OR (scope_type = 'DEPARTMENT'
                        AND scope_department_id IS NOT NULL AND scope_department_group_id IS NULL)
                    OR (scope_type = 'DEPARTMENT_GROUP'
                        AND scope_department_group_id IS NOT NULL AND scope_department_id IS NULL)
                )
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pva_active_target_user
            ON public.personnel_visibility_assignments (target_user_id)
            WHERE is_active = TRUE AND target_type = 'USER'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pva_active_target_position
            ON public.personnel_visibility_assignments (target_position_id)
            WHERE is_active = TRUE AND target_type = 'POSITION'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pva_active_target_department
            ON public.personnel_visibility_assignments (target_department_id)
            WHERE is_active = TRUE AND target_type = 'DEPARTMENT'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pva_created_at
            ON public.personnel_visibility_assignments (created_at DESC)
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.personnel_visibility_assignments IS
            'ADR-042 E1: visibility scope for org sidebar / personnel directory (read-only by default).'
        """
    )

    sal_types_sql = ", ".join(f"'{t}'" for t in _SAL_EVENT_TYPES)
    op.execute(
        """
        ALTER TABLE public.security_audit_log
            DROP CONSTRAINT IF EXISTS chk_sal_event_type
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.security_audit_log
            ADD CONSTRAINT chk_sal_event_type
                CHECK (event_type IN ({sal_types_sql}))
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.personnel_visibility_assignments CASCADE")

    sal_types_sql = ", ".join(
        f"'{t}'"
        for t in _SAL_EVENT_TYPES
        if t not in ("VISIBILITY_GRANTED", "VISIBILITY_REVOKED")
    )
    op.execute(
        """
        ALTER TABLE public.security_audit_log
            DROP CONSTRAINT IF EXISTS chk_sal_event_type
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.security_audit_log
            ADD CONSTRAINT chk_sal_event_type
                CHECK (event_type IN ({sal_types_sql}))
        """
    )
