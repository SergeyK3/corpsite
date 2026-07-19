"""Register HR_IMPORT_REVIEW_COMPLETED security audit event type.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
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
)

_SAL_EVENT_TYPES_DOWN = tuple(t for t in _SAL_EVENT_TYPES if t != "HR_IMPORT_REVIEW_COMPLETED")


def _count_hr_import_review_completed_rows(bind) -> int:
    row = bind.execute(
        text(
            """
            SELECT COUNT(*)::bigint
            FROM public.security_audit_log
            WHERE event_type = 'HR_IMPORT_REVIEW_COMPLETED'
            """
        )
    ).scalar()
    return int(row or 0)


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
    bind = op.get_bind()
    row_count = _count_hr_import_review_completed_rows(bind)
    if row_count > 0:
        raise RuntimeError(
            "Downgrade of revision d5e6f7a8b9c0 is blocked: "
            f"security_audit_log contains {row_count} HR_IMPORT_REVIEW_COMPLETED row(s)."
        )

    sal_types_sql = ", ".join(f"'{t}'" for t in _SAL_EVENT_TYPES_DOWN)
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
