"""Register EMPLOYEE_HARD_DELETED security audit event type.

Revision ID: a9b0c1d2e3f4
Revises: q8r9s0t1u2v3
"""
from __future__ import annotations

from alembic import op

revision = "a9b0c1d2e3f4"
down_revision = "q8r9s0t1u2v3"
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
    "EMPLOYEE_ENROLLED_FROM_IMPORT",
    "HR_IMPORT_REVIEW_COMPLETED",
    "EDITORIAL_GENERATED",
    "EDITORIAL_REGENERATED",
    "EDITORIAL_OVERRIDE_UPDATED",
    "EDITORIAL_OVERRIDE_CLEARED",
    "EDITORIAL_MARKED_STALE",
    "READY_GATE_REJECTED",
    "ORG_UNIT_CREATED",
    "ORG_UNIT_UPDATED",
    "ORG_UNIT_ACTIVATED",
    "ORG_UNIT_DEACTIVATED",
    "ORG_UNIT_DELETED",
    "ORG_UNIT_DELETE_REJECTED",
    "EMPLOYEE_HARD_DELETED",
)

_SAL_EVENT_TYPES_DOWN = tuple(t for t in _SAL_EVENT_TYPES if t != "EMPLOYEE_HARD_DELETED")


def _apply_event_types(types: tuple[str, ...]) -> None:
    sal_types_sql = ", ".join(f"'{t}'" for t in types)
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


def upgrade() -> None:
    _apply_event_types(_SAL_EVENT_TYPES)


def downgrade() -> None:
    _apply_event_types(_SAL_EVENT_TYPES_DOWN)
