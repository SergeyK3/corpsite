"""regular_task_run_items_v2_add_fields

Revision ID: 573bfd246238
Revises: 24b1dc1801ef
Create Date: 2026-02-08 15:41:34.783019
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "573bfd246238"
down_revision: Union[str, Sequence[str], None] = "24b1dc1801ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: Align DB schema with app/services/regular_tasks_service.py expectations.
    # The service writes: period_id, executor_role_id, is_due, created_tasks, status, error, meta.

    # 1) Add missing columns (idempotent enough for fresh dev DBs; if already exists, Alembic will error).
    op.add_column("regular_task_run_items", sa.Column("period_id", sa.BigInteger(), nullable=True))
    op.add_column("regular_task_run_items", sa.Column("executor_role_id", sa.BigInteger(), nullable=True))

    op.add_column(
        "regular_task_run_items",
        sa.Column("is_due", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "regular_task_run_items",
        sa.Column("created_tasks", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("regular_task_run_items", sa.Column("error", sa.Text(), nullable=True))

    # Prefer jsonb (service uses '{}'::jsonb in other places; Postgres supports jsonb indexing if needed)
    op.add_column(
        "regular_task_run_items",
        sa.Column("meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    # 2) Indexes for common drill-down/debug queries
    op.create_index(
        "ix_regular_task_run_items_period_id",
        "regular_task_run_items",
        ["period_id"],
    )
    op.create_index(
        "ix_regular_task_run_items_executor_role_id",
        "regular_task_run_items",
        ["executor_role_id"],
    )

    # 3) Drop server defaults we only needed for backfilling existing rows
    op.alter_column("regular_task_run_items", "is_due", server_default=None)
    op.alter_column("regular_task_run_items", "created_tasks", server_default=None)
    op.alter_column("regular_task_run_items", "meta", server_default=None)


def downgrade() -> None:
    # Reverse order: drop indexes first, then columns
    op.drop_index("ix_regular_task_run_items_executor_role_id", table_name="regular_task_run_items")
    op.drop_index("ix_regular_task_run_items_period_id", table_name="regular_task_run_items")

    op.drop_column("regular_task_run_items", "meta")
    op.drop_column("regular_task_run_items", "error")
    op.drop_column("regular_task_run_items", "created_tasks")
    op.drop_column("regular_task_run_items", "is_due")
    op.drop_column("regular_task_run_items", "executor_role_id")
    op.drop_column("regular_task_run_items", "period_id")
