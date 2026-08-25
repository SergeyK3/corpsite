"""allow leave types as personnel order headers

Revision ID: r1s2t3u4v5w6
Revises: p1q2r3s4t5u6
"""
from alembic import op


revision = "r1s2t3u4v5w6"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None


_BASE_TYPES = (
    "'HIRE', 'TRANSFER', 'TERMINATION', "
    "'CONCURRENT_DUTY_START', 'CONCURRENT_DUTY_END', 'COMPOSITE'"
)
_LEAVE_TYPES = _BASE_TYPES + ", 'LEAVE.ANNUAL.GRANT', 'LEAVE.UNPAID.GRANT'"


def _replace_constraint(types: str) -> None:
    op.execute("ALTER TABLE public.personnel_orders DROP CONSTRAINT IF EXISTS chk_personnel_orders_order_type_code")
    op.execute(
        "ALTER TABLE public.personnel_orders "
        "ADD CONSTRAINT chk_personnel_orders_order_type_code "
        f"CHECK (order_type_code IN ({types}))"
    )


def upgrade() -> None:
    _replace_constraint(_LEAVE_TYPES)


def downgrade() -> None:
    _replace_constraint(_BASE_TYPES)
