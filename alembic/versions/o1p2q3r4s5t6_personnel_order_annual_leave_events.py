"""allow annual-leave events linked to personnel order items

Revision ID: o1p2q3r4s5t6
Revises: n1o2p3q4r5s6
"""
from alembic import op


revision = "o1p2q3r4s5t6"
down_revision = "n1o2p3q4r5s6"
branch_labels = None
depends_on = None


_PREVIOUS_EVENT_TYPES = (
    "'HIRE', 'TRANSFER', 'CORRECTION', 'TERMINATION', "
    "'POSITION_CHANGE', 'RATE_CHANGE', 'EMPLOYEE_ENROLLED_FROM_IMPORT'"
)
_EVENT_TYPES_WITH_ANNUAL_LEAVE = _PREVIOUS_EVENT_TYPES + ", 'ANNUAL_LEAVE'"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.employee_events "
        "DROP CONSTRAINT IF EXISTS chk_employee_events_event_type"
    )
    op.execute(
        "ALTER TABLE public.employee_events "
        "ADD CONSTRAINT chk_employee_events_event_type "
        f"CHECK (event_type IN ({_EVENT_TYPES_WITH_ANNUAL_LEAVE}))"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uq_employee_events_annual_leave_order_item "
        "ON public.employee_events (order_item_id) "
        "WHERE event_type = 'ANNUAL_LEAVE'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.uq_employee_events_annual_leave_order_item")
    op.execute(
        "ALTER TABLE public.employee_events "
        "DROP CONSTRAINT IF EXISTS chk_employee_events_event_type"
    )
    op.execute(
        "ALTER TABLE public.employee_events "
        "ADD CONSTRAINT chk_employee_events_event_type "
        f"CHECK (event_type IN ({_PREVIOUS_EVENT_TYPES}))"
    )
