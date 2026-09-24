"""Allow supplementary-pay draft headers after structured storage."""
from alembic import op


revision = "pojson002"
# This revision continues only the committed personnel-order storage chain.
down_revision = "pojson001"
branch_labels = None
depends_on = None


_PREVIOUS_TYPES = (
    "'HIRE', 'TRANSFER', 'TERMINATION', 'CONCURRENT_DUTY_START', "
    "'CONCURRENT_DUTY_END', 'COMPOSITE', 'LEAVE.ANNUAL.GRANT', "
    "'LEAVE.UNPAID.GRANT'"
)
_UPGRADED_TYPES = _PREVIOUS_TYPES + ", 'SUPPLEMENTARY_PAY'"


def _replace_constraint(types: str) -> None:
    op.execute(
        "ALTER TABLE public.personnel_orders "
        "DROP CONSTRAINT chk_personnel_orders_order_type_code"
    )
    op.execute(
        "ALTER TABLE public.personnel_orders "
        "ADD CONSTRAINT chk_personnel_orders_order_type_code "
        f"CHECK (order_type_code IN ({types}))"
    )


def upgrade() -> None:
    _replace_constraint(_UPGRADED_TYPES)


def downgrade() -> None:
    _replace_constraint(_PREVIOUS_TYPES)
