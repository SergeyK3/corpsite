"""ADR-044 R2.5d — register USER_EMPLOYEE_LINK_ROLLED_BACK audit event.

Revision ID: g6b7c8d9e0f1
Revises: f5a6b7c8d9e0
"""
from __future__ import annotations

from alembic import op

revision = "g6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None

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
    "USER_EMPLOYEE_LINKED",
    "USER_EMPLOYEE_UNLINKED",
    "USER_EMPLOYEE_LINK_ROLLED_BACK",
)


def upgrade() -> None:
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
    sal_types_sql = ", ".join(
        f"'{t}'"
        for t in _SAL_EVENT_TYPES
        if t != "USER_EMPLOYEE_LINK_ROLLED_BACK"
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
