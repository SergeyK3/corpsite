"""WP-PO-008 — Allow nullable registration fields on personnel_orders drafts.

Paper First process: order_number and order_date come from the paper journal and
may be filled after DRAFT creation. Registration still requires both fields
(enforced in personnel_orders_command_service._validate_registerable_order).
"""
from __future__ import annotations

from alembic import op

revision = "r2s3t4u5v6w7"
down_revision = "q1r2s3t4u5w6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.personnel_orders
            ALTER COLUMN order_number DROP NOT NULL,
            ALTER COLUMN order_date DROP NOT NULL
        """
    )


def downgrade() -> None:
    # Fail loudly if drafts without registration fields exist.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.personnel_orders
                WHERE order_number IS NULL
                   OR order_date IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade r2s3t4u5v6w7: personnel_orders has NULL order_number/order_date';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        ALTER TABLE public.personnel_orders
            ALTER COLUMN order_number SET NOT NULL,
            ALTER COLUMN order_date SET NOT NULL
        """
    )
