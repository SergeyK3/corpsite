"""seed task_statuses dictionary

Revision ID: 0003_seed_task_statuses
Revises: 0002_create_users_hierarchy
Create Date: 2026-01-02 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_seed_task_statuses"
down_revision = "0002_create_users_hierarchy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    task_statuses_table = sa.table(
        "task_statuses",
        sa.column("code", sa.String),
        sa.column("name_ru", sa.String),
        sa.column("is_terminal", sa.Boolean),
    )

    op.bulk_insert(
        task_statuses_table,
        [
            {
                "code": "INBOX",
                "name_ru": "Входящая",
                "is_terminal": False,
            },
            {
                "code": "IN_PROGRESS",
                "name_ru": "В работе",
                "is_terminal": False,
            },
            {
                "code": "WAITING_REPORT",
                "name_ru": "Ожидается отчёт",
                "is_terminal": False,
            },
            {
                "code": "WAITING_APPROVAL",
                "name_ru": "Ожидается согласование",
                "is_terminal": False,
            },
            {
                "code": "DONE",
                "name_ru": "Завершена",
                "is_terminal": True,
            },
            {
                "code": "ARCHIVED",
                "name_ru": "Архивирована",
                "is_terminal": True,
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM task_statuses
        WHERE code IN (
            'INBOX',
            'IN_PROGRESS',
            'WAITING_REPORT',
            'WAITING_APPROVAL',
            'DONE',
            'ARCHIVED'
        );
        """
    )
