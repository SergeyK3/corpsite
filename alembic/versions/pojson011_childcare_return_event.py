"""Allow applied childcare-return personnel-order events.

Revision ID: pojson011
Revises: pojson010
"""
from alembic import op


revision = "pojson011"
down_revision = "pojson010"
branch_labels = None
depends_on = None


_PREVIOUS_EVENT_TYPES = (
    "'HIRE', 'TRANSFER', 'CORRECTION', 'TERMINATION', "
    "'POSITION_CHANGE', 'RATE_CHANGE', 'EMPLOYEE_ENROLLED_FROM_IMPORT', "
    "'ANNUAL_LEAVE'"
)
_EVENT_TYPES = _PREVIOUS_EVENT_TYPES + ", 'LEAVE.CHILDCARE.RETURN'"


def _replace_event_type_check(event_types: str) -> None:
    op.execute(
        "ALTER TABLE public.employee_events "
        "DROP CONSTRAINT IF EXISTS chk_employee_events_event_type"
    )
    op.execute(
        "ALTER TABLE public.employee_events "
        "ADD CONSTRAINT chk_employee_events_event_type "
        f"CHECK (event_type IN ({event_types}))"
    )


def upgrade() -> None:
    _replace_event_type_check(_EVENT_TYPES)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uq_employee_events_childcare_return_order_item "
        "ON public.employee_events (order_item_id) "
        "WHERE event_type = 'LEAVE.CHILDCARE.RETURN'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.uq_employee_events_childcare_return_order_item")
    _replace_event_type_check(_PREVIOUS_EVENT_TYPES)
