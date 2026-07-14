"""Sysadmin org_units CRUD — register ORG_UNIT_* security audit event types.

Revision ID: h8i9j0k1l2m3
Revises: d4e5f6a7b8c9
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "h8i9j0k1l2m3"
down_revision = "d4e5f6a7b8c9"
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

_ORG_UNIT_AUDIT_EVENT_TYPES = (
    "ORG_UNIT_CREATED",
    "ORG_UNIT_UPDATED",
    "ORG_UNIT_ACTIVATED",
    "ORG_UNIT_DEACTIVATED",
    "ORG_UNIT_DELETED",
    "ORG_UNIT_DELETE_REJECTED",
)

_SAL_EVENT_TYPES_DOWN = tuple(
    t
    for t in _SAL_EVENT_TYPES
    if t not in set(_ORG_UNIT_AUDIT_EVENT_TYPES)
)


def _count_org_unit_audit_rows(bind) -> int:
    types_sql = ", ".join(f"'{event_type}'" for event_type in _ORG_UNIT_AUDIT_EVENT_TYPES)
    row = bind.execute(
        text(
            f"""
            SELECT COUNT(*)::bigint
            FROM public.security_audit_log
            WHERE event_type IN ({types_sql})
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
    org_unit_row_count = _count_org_unit_audit_rows(bind)
    if org_unit_row_count > 0:
        raise RuntimeError(
            "Downgrade of revision h8i9j0k1l2m3 is blocked: "
            f"security_audit_log contains {org_unit_row_count} ORG_UNIT_* audit row(s). "
            "Audit history must be archived or migrated separately before removing "
            "ORG_UNIT_* event types from chk_sal_event_type."
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
