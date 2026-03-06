# FILE: alembic/versions/74c285340058_adhoc_tasks_contract.py
"""adhoc tasks contract

Revision ID: 74c285340058
Revises: b17f7f69c7d5
Create Date: 2026-03-06 23:24:54.579245
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "74c285340058"
down_revision: Union[str, Sequence[str], None] = "b17f7f69c7d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TASK_KIND_VALUES = ("regular", "adhoc")
SOURCE_KIND_VALUES = ("regular_task", "manual", "bot", "import")


def upgrade() -> None:
    op.add_column("tasks", sa.Column("created_by_user_id", sa.BigInteger(), nullable=True))
    op.add_column("tasks", sa.Column("approver_user_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column(
            "task_kind",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'regular'"),
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "requires_report",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "requires_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "source_kind",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'regular_task'"),
        ),
    )
    op.add_column("tasks", sa.Column("source_note", sa.Text(), nullable=True))

    op.create_foreign_key(
        "fk_tasks_created_by_user",
        "tasks",
        "users",
        ["created_by_user_id"],
        ["user_id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_tasks_approver_user",
        "tasks",
        "users",
        ["approver_user_id"],
        ["user_id"],
        ondelete="SET NULL",
    )

    op.create_check_constraint(
        "ck_tasks_task_kind",
        "tasks",
        f"task_kind IN {TASK_KIND_VALUES}",
    )
    op.create_check_constraint(
        "ck_tasks_source_kind",
        "tasks",
        f"source_kind IN {SOURCE_KIND_VALUES}",
    )

    op.execute(
        """
        UPDATE public.tasks
        SET
            task_kind = CASE
                WHEN regular_task_id IS NULL THEN 'adhoc'
                ELSE 'regular'
            END,
            source_kind = CASE
                WHEN regular_task_id IS NULL THEN 'manual'
                ELSE 'regular_task'
            END
        """
    )

    op.alter_column("tasks", "task_kind", server_default=None)
    op.alter_column("tasks", "requires_report", server_default=None)
    op.alter_column("tasks", "requires_approval", server_default=None)
    op.alter_column("tasks", "source_kind", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_tasks_source_kind", "tasks", type_="check")
    op.drop_constraint("ck_tasks_task_kind", "tasks", type_="check")
    op.drop_constraint("fk_tasks_approver_user", "tasks", type_="foreignkey")
    op.drop_constraint("fk_tasks_created_by_user", "tasks", type_="foreignkey")

    op.drop_column("tasks", "source_note")
    op.drop_column("tasks", "source_kind")
    op.drop_column("tasks", "requires_approval")
    op.drop_column("tasks", "requires_report")
    op.drop_column("tasks", "task_kind")
    op.drop_column("tasks", "approver_user_id")
    op.drop_column("tasks", "created_by_user_id")