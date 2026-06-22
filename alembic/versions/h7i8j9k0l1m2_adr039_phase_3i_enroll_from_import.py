"""ADR-039 Phase 3I — EMPLOYEE_ENROLLED_FROM_IMPORT audit event types.

Revision ID: h7i8j9k0l1m2
Revises: g6b7c8d9e0f1
"""
from __future__ import annotations

from alembic import op

revision = "h7i8j9k0l1m2"
down_revision = "g6b7c8d9e0f1"
branch_labels = None
depends_on = None

_EMPLOYEE_EVENT_TYPES = (
    "HIRE",
    "TRANSFER",
    "CORRECTION",
    "TERMINATION",
    "POSITION_CHANGE",
    "RATE_CHANGE",
    "EMPLOYEE_ENROLLED_FROM_IMPORT",
)

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
    "EMPLOYEE_ENROLLED_FROM_IMPORT",
)


def upgrade() -> None:
    ee_types_sql = ", ".join(f"'{t}'" for t in _EMPLOYEE_EVENT_TYPES)
    op.execute(
        """
        ALTER TABLE public.employee_events
            DROP CONSTRAINT IF EXISTS chk_employee_events_event_type
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.employee_events
            ADD CONSTRAINT chk_employee_events_event_type CHECK (
                event_type IN ({ee_types_sql})
            )
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
    ee_types_sql = ", ".join(
        f"'{t}'" for t in _EMPLOYEE_EVENT_TYPES if t != "EMPLOYEE_ENROLLED_FROM_IMPORT"
    )
    op.execute(
        """
        ALTER TABLE public.employee_events
            DROP CONSTRAINT IF EXISTS chk_employee_events_event_type
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.employee_events
            ADD CONSTRAINT chk_employee_events_event_type CHECK (
                event_type IN ({ee_types_sql})
            )
        """
    )

    sal_types_sql = ", ".join(
        f"'{t}'" for t in _SAL_EVENT_TYPES if t != "EMPLOYEE_ENROLLED_FROM_IMPORT"
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
