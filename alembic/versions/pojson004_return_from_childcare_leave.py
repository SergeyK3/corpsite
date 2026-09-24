"""Allow the return-from-childcare-leave personnel-order type."""
from alembic import op


revision = "pojson004"
down_revision = "pojson003"
branch_labels = None
depends_on = None


_PREVIOUS_ITEM_TYPES = (
    "'HIRE', 'TRANSFER', 'TERMINATION', 'CONCURRENT_DUTY_START', "
    "'CONCURRENT_DUTY_END', 'LEAVE.ANNUAL.GRANT', "
    "'LEAVE.UNPAID.GRANT', 'SUPPLEMENTARY_PAY'"
)
_PREVIOUS_HEADER_TYPES = _PREVIOUS_ITEM_TYPES + ", 'COMPOSITE'"
_UPGRADED_ITEM_TYPES = _PREVIOUS_ITEM_TYPES + ", 'RETURN_FROM_CHILDCARE_LEAVE'"
_UPGRADED_HEADER_TYPES = _PREVIOUS_HEADER_TYPES + ", 'RETURN_FROM_CHILDCARE_LEAVE'"


def _replace(table: str, constraint: str, types: str) -> None:
    op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT IF EXISTS {constraint}")
    column = "order_type_code" if table == "personnel_orders" else "item_type_code"
    op.execute(f"ALTER TABLE public.{table} ADD CONSTRAINT {constraint} CHECK ({column} IN ({types}))")


def upgrade() -> None:
    _replace("personnel_orders", "chk_personnel_orders_order_type_code", _UPGRADED_HEADER_TYPES)
    _replace("personnel_order_items", "chk_personnel_order_items_item_type_code", _UPGRADED_ITEM_TYPES)


def downgrade() -> None:
    _replace("personnel_orders", "chk_personnel_orders_order_type_code", _PREVIOUS_HEADER_TYPES)
    _replace("personnel_order_items", "chk_personnel_order_items_item_type_code", _PREVIOUS_ITEM_TYPES)
