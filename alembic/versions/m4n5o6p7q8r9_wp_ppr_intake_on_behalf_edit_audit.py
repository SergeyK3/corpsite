"""Add intake_edited_on_behalf lifecycle audit action."""
from __future__ import annotations

from alembic import op

revision = "m4n5o6p7q8r9"
down_revision = "l3m4n5o6p7q8"
branch_labels = None
depends_on = None

_LIFECYCLE_ACTIONS = (
    "registered",
    "intake_link_issued",
    "intake_opened",
    "intake_submitted",
    "intake_edited_on_behalf",
    "review_started",
    "review_completed",
    "intake_transferred",
    "resolution_opened",
    "resolution_recorded",
    "resolution_changed",
    "resolution_reopened",
    "hire_order_draft_created",
    "hire_applied",
    "completed",
    "rejected",
    "cancelled",
    "expired",
)


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    actions_sql = _sql_tuple(_LIFECYCLE_ACTIONS)
    op.execute(
        "ALTER TABLE public.personnel_application_lifecycle_audit "
        "DROP CONSTRAINT IF EXISTS chk_personnel_application_lifecycle_audit_action"
    )
    op.execute(
        f"""
        ALTER TABLE public.personnel_application_lifecycle_audit
            ADD CONSTRAINT chk_personnel_application_lifecycle_audit_action
                CHECK (action IN ({actions_sql}))
        """
    )


def downgrade() -> None:
    actions_sql = _sql_tuple(
        tuple(action for action in _LIFECYCLE_ACTIONS if action != "intake_edited_on_behalf")
    )
    op.execute(
        "DELETE FROM public.personnel_application_lifecycle_audit "
        "WHERE action = 'intake_edited_on_behalf'"
    )
    op.execute(
        "ALTER TABLE public.personnel_application_lifecycle_audit "
        "DROP CONSTRAINT IF EXISTS chk_personnel_application_lifecycle_audit_action"
    )
    op.execute(
        f"""
        ALTER TABLE public.personnel_application_lifecycle_audit
            ADD CONSTRAINT chk_personnel_application_lifecycle_audit_action
                CHECK (action IN ({actions_sql}))
        """
    )
