"""merge alembic heads; ensure task_event_type enum on restored DBs

Revision ID: a7c4e1f903de
Revises: d668fb72f5f7
Create Date: 2026-06-08

Repairs VPS databases where alembic skipped 9d9d8a6c2a11 (file had no .py suffix).
write_task_audit() casts event_type to ::task_event_type; without the enum POST /report returns 500.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "a7c4e1f903de"
down_revision: Union[str, Sequence[str], None] = "d668fb72f5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        r"""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_event_type') THEN
            CREATE TYPE public.task_event_type AS ENUM (
              'REPORT_SUBMITTED',
              'APPROVED',
              'REJECTED',
              'ARCHIVED'
            );
          END IF;
        END $$;
        """
    )

    op.execute(
        r"""
        INSERT INTO public.task_statuses (code, name_ru)
        SELECT v.code, v.name_ru
        FROM (VALUES
          ('IN_PROGRESS',      'В работе'),
          ('WAITING_REPORT',   'Ожидает отчёт'),
          ('WAITING_APPROVAL', 'Ожидает согласование'),
          ('DONE',             'Выполнено'),
          ('REJECTED',         'Отклонено'),
          ('ARCHIVED',         'В архиве')
        ) AS v(code, name_ru)
        WHERE NOT EXISTS (
          SELECT 1 FROM public.task_statuses ts WHERE ts.code = v.code
        );
        """
    )


def downgrade() -> None:
    pass
