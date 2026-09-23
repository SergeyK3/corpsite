"""Add common structured storage to personnel order headers.

The field is intentionally nullable-free only through its empty JSON default;
existing order_number and order_date values remain nullable for legacy drafts.
"""
from alembic import op


revision = "pojson001"
down_revision = "hdc001checklist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.personnel_orders
            ADD COLUMN IF NOT EXISTS storage_json JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.personnel_orders DROP COLUMN IF EXISTS storage_json"
    )
