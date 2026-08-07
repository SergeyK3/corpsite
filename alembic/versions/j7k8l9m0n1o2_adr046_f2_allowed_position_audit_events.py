"""Register ADR-046 F2 allowed-position security audit event types.

Revision ID: j7k8l9m0n1o2
Revises: i6j7k8l9m0n1
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "j7k8l9m0n1o2"
down_revision = "i6j7k8l9m0n1"
branch_labels = None
depends_on = None

_PRE_F2_EVENT_TYPES = (
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

_F2_EVENT_TYPES = (
    "ORG_UNIT_ALLOWED_POSITION_CREATED",
    "ORG_UNIT_ALLOWED_POSITION_REACTIVATED",
    "ORG_UNIT_ALLOWED_POSITION_UPDATED",
    "ORG_UNIT_ALLOWED_POSITION_DEACTIVATED",
)

_EXTENDED_EVENT_TYPES = _PRE_F2_EVENT_TYPES + _F2_EVENT_TYPES


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


def _f2_event_counts(bind) -> dict[str, int]:
    event_types_sql = ", ".join(f"'{event_type}'" for event_type in _F2_EVENT_TYPES)
    rows = bind.execute(
        text(
            f"""
            SELECT event_type, COUNT(*)::bigint AS row_count
            FROM public.security_audit_log
            WHERE event_type IN ({event_types_sql})
            GROUP BY event_type
            """
        )
    ).all()
    present = {str(row.event_type): int(row.row_count) for row in rows}
    return {event_type: present.get(event_type, 0) for event_type in _F2_EVENT_TYPES}


def upgrade() -> None:
    _replace_event_type_check(_EXTENDED_EVENT_TYPES)


def downgrade() -> None:
    # This guard is intentionally evaluated before any CHECK DDL. Audit history
    # is never deleted or rewritten by this migration.
    counts = _f2_event_counts(op.get_bind())
    blocking_counts = {event_type: count for event_type, count in counts.items() if count > 0}
    if blocking_counts:
        details = ", ".join(
            f"{event_type}={count}" for event_type, count in blocking_counts.items()
        )
        raise RuntimeError(
            "Downgrade of revision j7k8l9m0n1o2 is blocked: "
            f"security_audit_log contains ADR-046 F2 audit rows ({details}). "
            "Audit history must be preserved; chk_sal_event_type was not changed."
        )

    _replace_event_type_check(_PRE_F2_EVENT_TYPES)
