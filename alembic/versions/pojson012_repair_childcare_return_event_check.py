"""Repair the employee-event CHECK for childcare-return order events.

Revision ID: pojson012
Revises: pojson011
"""
from alembic import op


revision = "pojson012"
down_revision = "pojson011"
branch_labels = None
depends_on = None


_ALLOWED_EVENT_TYPES = (
    "'HIRE', 'TRANSFER', 'CORRECTION', 'TERMINATION', "
    "'POSITION_CHANGE', 'RATE_CHANGE', 'EMPLOYEE_ENROLLED_FROM_IMPORT', "
    "'ANNUAL_LEAVE', 'LEAVE.CHILDCARE.RETURN'"
)


def _replace_event_type_check() -> None:
    op.execute(
        "ALTER TABLE public.employee_events "
        "DROP CONSTRAINT IF EXISTS chk_employee_events_event_type"
    )
    op.execute(
        "ALTER TABLE public.employee_events "
        "ADD CONSTRAINT chk_employee_events_event_type "
        f"CHECK (event_type IN ({_ALLOWED_EVENT_TYPES}))"
    )


def upgrade() -> None:
    _replace_event_type_check()


def downgrade() -> None:
    # pojson011's intended schema has the same allowed event types.
    _replace_event_type_check()
