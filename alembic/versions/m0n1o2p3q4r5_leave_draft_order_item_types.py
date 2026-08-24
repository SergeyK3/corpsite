"""allow minimal leave draft item types

Revision ID: m0n1o2p3q4r5
Revises: k8l9m0n1o2p3
"""

from alembic import op

revision = "m0n1o2p3q4r5"
down_revision = "k8l9m0n1o2p3"
branch_labels = None
depends_on = None

_TYPES = (
    "'HIRE', 'TRANSFER', 'TERMINATION', "
    "'CONCURRENT_DUTY_START', 'CONCURRENT_DUTY_END', "
    "'LEAVE.ANNUAL.GRANT', 'LEAVE.UNPAID.GRANT'"
)
_MVP_TYPES = (
    "'HIRE', 'TRANSFER', 'TERMINATION', "
    "'CONCURRENT_DUTY_START', 'CONCURRENT_DUTY_END'"
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.personnel_order_items "
        "DROP CONSTRAINT IF EXISTS "
        "chk_personnel_order_items_item_type_code"
    )
    op.execute(
        "ALTER TABLE public.personnel_order_items "
        "ADD CONSTRAINT chk_personnel_order_items_item_type_code "
        f"CHECK (item_type_code IN ({_TYPES}))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.personnel_order_items "
        "DROP CONSTRAINT IF EXISTS "
        "chk_personnel_order_items_item_type_code"
    )
    op.execute(
        "ALTER TABLE public.personnel_order_items "
        "ADD CONSTRAINT chk_personnel_order_items_item_type_code "
        f"CHECK (item_type_code IN ({_MVP_TYPES}))"
    )
