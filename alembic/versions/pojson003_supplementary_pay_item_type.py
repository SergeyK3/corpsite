"""Allow supplementary-pay draft items."""
from alembic import op


revision = "pojson003"
down_revision = "pojson002"
branch_labels = None
depends_on = None


_PREVIOUS_TYPES = (
    "'HIRE', 'TRANSFER', 'TERMINATION', 'CONCURRENT_DUTY_START', "
    "'CONCURRENT_DUTY_END', 'LEAVE.ANNUAL.GRANT', "
    "'LEAVE.UNPAID.GRANT'"
)
_UPGRADED_TYPES = _PREVIOUS_TYPES + ", 'SUPPLEMENTARY_PAY'"


def _replace_constraint(types: str) -> None:
    op.execute(
        "ALTER TABLE public.personnel_order_items "
        "DROP CONSTRAINT chk_personnel_order_items_item_type_code"
    )
    op.execute(
        "ALTER TABLE public.personnel_order_items "
        "ADD CONSTRAINT chk_personnel_order_items_item_type_code "
        f"CHECK (item_type_code IN ({types}))"
    )


def upgrade() -> None:
    _replace_constraint(_UPGRADED_TYPES)


def downgrade() -> None:
    _replace_constraint(_PREVIOUS_TYPES)
