"""upsert task_statuses dictionary (name_ru, is_terminal)

Revision ID: 0004_upsert_task_statuses
Revises: 0003_seed_task_statuses
Create Date: 2026-01-02 00:00:00.000000
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "0004_upsert_task_statuses"
down_revision = "0003_seed_task_statuses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO task_statuses (code, name_ru, is_terminal)
        VALUES
            ('INBOX', 'Входящая', false),
            ('IN_PROGRESS', 'В работе', false),
            ('WAITING_REPORT', 'Ожидается отчёт', false),
            ('WAITING_APPROVAL', 'Ожидается согласование', false),
            ('DONE', 'Завершена', true),
            ('ARCHIVED', 'Архивирована', true)
        ON CONFLICT (code) DO UPDATE
        SET
            name_ru = EXCLUDED.name_ru,
            is_terminal = EXCLUDED.is_terminal;
        """
    )


def downgrade() -> None:
    # Downgrade intentionally does nothing:
    # statuses may be in use as FK in tasks/status history.
    pass
