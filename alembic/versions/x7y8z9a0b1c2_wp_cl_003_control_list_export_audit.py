"""WP-CL-003: register the control-list export audit event.

Revision ID: x7y8z9a0b1c2
Revises: w6x7y8z9a0b1
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "x7y8z9a0b1c2"
down_revision = "w6x7y8z9a0b1"
branch_labels = None
depends_on = None

_PREVIOUS_EVENT_TYPES = (
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
    "ORG_UNIT_ALLOWED_POSITION_CREATED",
    "ORG_UNIT_ALLOWED_POSITION_REACTIVATED",
    "ORG_UNIT_ALLOWED_POSITION_UPDATED",
    "ORG_UNIT_ALLOWED_POSITION_DEACTIVATED",
    "EMPLOYEE_HARD_DELETED",
)
_EVENT_TYPE = "CONTROL_LIST_EXPORT"
_EXTENDED_EVENT_TYPES = _PREVIOUS_EVENT_TYPES + (_EVENT_TYPE,)


def _replace_event_type_check(event_types: tuple[str, ...]) -> None:
    event_types_sql = ", ".join(f"'{event_type}'" for event_type in event_types)
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
                CHECK (event_type IN ({event_types_sql}))
        """
    )


def upgrade() -> None:
    _replace_event_type_check(_EXTENDED_EVENT_TYPES)


def downgrade() -> None:
    row_count = int(
        op.get_bind()
        .execute(
            text(
                """
                SELECT COUNT(*)::bigint
                FROM public.security_audit_log
                WHERE event_type = :event_type
                """
            ),
            {"event_type": _EVENT_TYPE},
        )
        .scalar_one()
    )
    if row_count:
        raise RuntimeError(
            "Downgrade of revision x7y8z9a0b1c2 is blocked: "
            "control-list export audit history must be preserved."
        )
    _replace_event_type_check(_PREVIOUS_EVENT_TYPES)
