"""Append-only acknowledgement events for personnel orders."""
from alembic import op
import sqlalchemy as sa

revision = "pojson006"
down_revision = "pojson005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "personnel_order_acknowledgement_events",
        sa.Column("acknowledgement_event_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger(), sa.ForeignKey("personnel_orders.order_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("employee_id", sa.BigInteger(), sa.ForeignKey("employees.employee_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("acknowledged_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False),
        sa.CheckConstraint("event_type IN ('RECORDED', 'CORRECTED', 'CLEARED')", name="chk_personnel_order_ack_event_type"),
        sa.CheckConstraint("(event_type = 'CLEARED' AND acknowledged_on IS NULL) OR (event_type IN ('RECORDED', 'CORRECTED') AND acknowledged_on IS NOT NULL)", name="chk_personnel_order_ack_event_date"),
    )
    op.create_index("ix_personnel_order_ack_events_order_employee_created", "personnel_order_acknowledgement_events", ["order_id", "employee_id", "created_at", "acknowledgement_event_id"])


def downgrade() -> None:
    op.drop_index("ix_personnel_order_ack_events_order_employee_created", table_name="personnel_order_acknowledgement_events")
    op.drop_table("personnel_order_acknowledgement_events")
