"""create periods, task_statuses, tasks

Revision ID: 0001_create_periods_tasks_statuses
Revises: 
Create Date: 2026-01-02 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_create_periods_tasks_statuses"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- periods ---
    op.create_table(
        "periods",
        sa.Column("period_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("period_type", sa.String(length=16), nullable=False),  # WEEK / MONTH / YEAR
        sa.Column("date_start", sa.Date(), nullable=False),
        sa.Column("date_end", sa.Date(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),  # e.g. "2026-01"
        sa.Column("status", sa.String(length=16), nullable=False, server_default="OPEN"),  # OPEN / CLOSED
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_periods_period_type", "periods", ["period_type"], unique=False)
    op.create_index("ix_periods_date_start", "periods", ["date_start"], unique=False)
    op.create_index("ix_periods_code", "periods", ["code"], unique=True)

    # --- task_statuses ---
    op.create_table(
        "task_statuses",
        sa.Column("status_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),  # IN_PROGRESS / WAITING_REPORT ...
        sa.Column("name_ru", sa.String(length=255), nullable=False),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_task_statuses_code", "task_statuses", ["code"], unique=True)

    # --- tasks ---
    op.create_table(
        "tasks",
        sa.Column("task_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("parent_task_id", sa.BigInteger(), nullable=True),
        sa.Column("period_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("initiator_user_id", sa.BigInteger(), nullable=False),
        sa.Column("executor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("status_id", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_task_id"],
            ["tasks.task_id"],
            name="fk_tasks_parent_task_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["period_id"],
            ["periods.period_id"],
            name="fk_tasks_period_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["status_id"],
            ["task_statuses.status_id"],
            name="fk_tasks_status_id",
            ondelete="RESTRICT",
        ),
        # NOTE: user FK constraints are intentionally omitted here, because users table
        # may be in a different revision/module. Add them when users table exists.
    )

    op.create_index("ix_tasks_period_id", "tasks", ["period_id"], unique=False)
    op.create_index("ix_tasks_status_id", "tasks", ["status_id"], unique=False)
    op.create_index("ix_tasks_executor_user_id", "tasks", ["executor_user_id"], unique=False)
    op.create_index("ix_tasks_initiator_user_id", "tasks", ["initiator_user_id"], unique=False)
    op.create_index("ix_tasks_parent_task_id", "tasks", ["parent_task_id"], unique=False)

    # Optional helpful composite indexes for common filters
    op.create_index("ix_tasks_period_status", "tasks", ["period_id", "status_id"], unique=False)
    op.create_index("ix_tasks_executor_status", "tasks", ["executor_user_id", "status_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tasks_executor_status", table_name="tasks")
    op.drop_index("ix_tasks_period_status", table_name="tasks")
    op.drop_index("ix_tasks_parent_task_id", table_name="tasks")
    op.drop_index("ix_tasks_initiator_user_id", table_name="tasks")
    op.drop_index("ix_tasks_executor_user_id", table_name="tasks")
    op.drop_index("ix_tasks_status_id", table_name="tasks")
    op.drop_index("ix_tasks_period_id", table_name="tasks")
    op.drop_table("tasks")

    op.drop_index("ix_task_statuses_code", table_name="task_statuses")
    op.drop_table("task_statuses")

    op.drop_index("ix_periods_code", table_name="periods")
    op.drop_index("ix_periods_date_start", table_name="periods")
    op.drop_index("ix_periods_period_type", table_name="periods")
    op.drop_table("periods")
