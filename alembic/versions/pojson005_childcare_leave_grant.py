"""Allow the distinct childcare-leave grant personnel-order type.

The code follows the committed pojson chain and changes only check
constraints; it never rewrites existing orders or editorial blocks.
"""
from alembic import op


revision = "pojson005"
down_revision = "pojson004"
branch_labels = None
depends_on = None


_PREVIOUS_ITEM_TYPES = (
    "'HIRE', 'TRANSFER', 'TERMINATION', 'CONCURRENT_DUTY_START', "
    "'CONCURRENT_DUTY_END', 'LEAVE.ANNUAL.GRANT', 'LEAVE.UNPAID.GRANT', "
    "'SUPPLEMENTARY_PAY', 'RETURN_FROM_CHILDCARE_LEAVE'"
)
_PREVIOUS_HEADER_TYPES = _PREVIOUS_ITEM_TYPES + ", 'COMPOSITE'"
_UPGRADED_ITEM_TYPES = _PREVIOUS_ITEM_TYPES + ", 'LEAVE.CHILDCARE.GRANT'"
_UPGRADED_HEADER_TYPES = _PREVIOUS_HEADER_TYPES + ", 'LEAVE.CHILDCARE.GRANT'"


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
