# FILE: alembic/versions/20260127_adr020_regular_tasks_v1.py
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "20260127_adr020_regular_tasks_v1"
down_revision = "89e6f63718bc"  # <-- ВАЖНО: привяжем к существующей голове, чтобы не плодить heads
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    return bool(
        conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = :name
                """
            ),
            {"name": name},
        ).scalar()
    )


def _col_exists(table: str, col: str) -> bool:
    conn = op.get_bind()
    return bool(
        conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :t
                  AND column_name = :c
                """
            ),
            {"t": table, "c": col},
        ).scalar()
    )


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    return bool(
        conn.execute(
            text(
                """
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = :name
                """
            ),
            {"name": name},
        ).scalar()
    )


def upgrade() -> None:
    conn = op.get_bind()

    # 1) Таблица regular_tasks: создаём, если её вообще нет
    if not _table_exists("regular_tasks"):
        op.create_table(
            "regular_tasks",
            sa.Column("regular_task_id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("code", sa.Text(), nullable=True),
            sa.Column("executor_role_id", sa.BigInteger(), nullable=False),
            sa.Column("assignment_scope", sa.Text(), nullable=False, server_default=sa.text("'functional'")),
            sa.Column("schedule_type", sa.Text(), nullable=False),
            sa.Column(
                "schedule_params",
                sa.dialects.postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("create_offset_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("due_offset_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    # 2) Таблица есть, но может быть старого формата: ДОБАВЛЯЕМ недостающие колонки

    if not _col_exists("regular_tasks", "code"):
        op.add_column("regular_tasks", sa.Column("code", sa.Text(), nullable=True))

    # executor_role_id (если отсутствует) — добавляем как nullable, затем заполняем, затем делаем NOT NULL если возможно
    if not _col_exists("regular_tasks", "executor_role_id"):
        op.add_column("regular_tasks", sa.Column("executor_role_id", sa.BigInteger(), nullable=True))
        # заполним "заглушкой" (0) чтобы не падать; позже заменим на реальную роль через апдейт данных
        conn.execute(text("UPDATE public.regular_tasks SET executor_role_id = 0 WHERE executor_role_id IS NULL"))

    if not _col_exists("regular_tasks", "assignment_scope"):
        op.add_column(
            "regular_tasks",
            sa.Column("assignment_scope", sa.Text(), nullable=False, server_default=sa.text("'functional'")),
        )

    if not _col_exists("regular_tasks", "schedule_type"):
        op.add_column("regular_tasks", sa.Column("schedule_type", sa.Text(), nullable=True))
        conn.execute(text("UPDATE public.regular_tasks SET schedule_type = 'monthly' WHERE schedule_type IS NULL"))

    if not _col_exists("regular_tasks", "schedule_params"):
        op.add_column(
            "regular_tasks",
            sa.Column(
                "schedule_params",
                sa.dialects.postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    if not _col_exists("regular_tasks", "create_offset_days"):
        op.add_column(
            "regular_tasks",
            sa.Column("create_offset_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        )

    if not _col_exists("regular_tasks", "due_offset_days"):
        op.add_column(
            "regular_tasks",
            sa.Column("due_offset_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        )

    if not _col_exists("regular_tasks", "created_by_user_id"):
        op.add_column("regular_tasks", sa.Column("created_by_user_id", sa.BigInteger(), nullable=True))

    if not _col_exists("regular_tasks", "created_at"):
        op.add_column(
            "regular_tasks",
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _col_exists("regular_tasks", "updated_at"):
        op.add_column(
            "regular_tasks",
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    # 3) Индексы — создаём ТОЛЬКО если колонка есть
    if _col_exists("regular_tasks", "is_active") and (not _index_exists("ix_regular_tasks_active")):
        op.create_index("ix_regular_tasks_active", "regular_tasks", ["is_active"])

    if _col_exists("regular_tasks", "executor_role_id") and (not _index_exists("ix_regular_tasks_executor_role_id")):
        op.create_index("ix_regular_tasks_executor_role_id", "regular_tasks", ["executor_role_id"])

    if _col_exists("regular_tasks", "schedule_type") and (not _index_exists("ix_regular_tasks_schedule_type")):
        op.create_index("ix_regular_tasks_schedule_type", "regular_tasks", ["schedule_type"])

    # Уникальный code (partial unique where code is not null)
    if _col_exists("regular_tasks", "code") and (not _index_exists("ux_regular_tasks_code")):
        op.create_index(
            "ux_regular_tasks_code",
            "regular_tasks",
            ["code"],
            unique=True,
            postgresql_where=sa.text("code IS NOT NULL"),
        )

    # 4) regular_task_runs — общий журнал запусков генерации (уже используется сервисом)
    if not _table_exists("regular_task_runs"):
        op.create_table(
            "regular_task_runs",
            sa.Column("run_id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'ok'")),
            sa.Column("stats", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("errors", sa.dialects.postgresql.JSONB(), nullable=True),
        )

    if not _index_exists("ix_regular_task_runs_started_at"):
        op.create_index("ix_regular_task_runs_started_at", "regular_task_runs", ["started_at"])

    # 4.1) regular_task_run_items — ЖУРНАЛ ПО ШАБЛОНАМ (то, чего не хватало для UI/проверки)
    # хранит результат обработки каждого regular_task в рамках конкретного run_id
    if not _table_exists("regular_task_run_items"):
        op.create_table(
            "regular_task_run_items",
            sa.Column("run_item_id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "run_id",
                sa.BigInteger(),
                sa.ForeignKey("public.regular_task_runs.run_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "regular_task_id",
                sa.BigInteger(),
                sa.ForeignKey("public.regular_tasks.regular_task_id", ondelete="CASCADE"),
                nullable=False,
            ),
            # контекст (полезно для дебага/отчётов)
            sa.Column("period_id", sa.BigInteger(), nullable=True),
            sa.Column("executor_role_id", sa.BigInteger(), nullable=True),
            # результат
            sa.Column("is_due", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_tasks", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'ok'")),  # ok|skip|error
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("meta", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _index_exists("ix_regular_task_run_items_run_id"):
        op.create_index("ix_regular_task_run_items_run_id", "regular_task_run_items", ["run_id"])

    if not _index_exists("ix_regular_task_run_items_regular_task_id"):
        op.create_index("ix_regular_task_run_items_regular_task_id", "regular_task_run_items", ["regular_task_id"])

    # Для выборки "последние запуски по шаблону" (карточка UI)
    if not _index_exists("ix_regular_task_run_items_rt_run"):
        op.create_index(
            "ix_regular_task_run_items_rt_run",
            "regular_task_run_items",
            ["regular_task_id", "run_id"],
        )

    # 5) Dedupe-index на tasks (если таблица/колонки есть)
    if (
        _table_exists("tasks")
        and _col_exists("tasks", "regular_task_id")
        and _col_exists("tasks", "period_id")
        and _col_exists("tasks", "executor_role_id")
    ):
        if not _index_exists("ux_tasks_regular_period_executor"):
            op.create_index(
                "ux_tasks_regular_period_executor",
                "tasks",
                ["regular_task_id", "period_id", "executor_role_id"],
                unique=True,
            )


def downgrade() -> None:
    # Для dev можно; на prod лучше делать отдельные миграции на удаление.

    if _index_exists("ux_tasks_regular_period_executor"):
        op.drop_index("ux_tasks_regular_period_executor", table_name="tasks")

    if _index_exists("ix_regular_task_run_items_rt_run"):
        op.drop_index("ix_regular_task_run_items_rt_run", table_name="regular_task_run_items")
    if _index_exists("ix_regular_task_run_items_regular_task_id"):
        op.drop_index("ix_regular_task_run_items_regular_task_id", table_name="regular_task_run_items")
    if _index_exists("ix_regular_task_run_items_run_id"):
        op.drop_index("ix_regular_task_run_items_run_id", table_name="regular_task_run_items")
    if _table_exists("regular_task_run_items"):
        op.drop_table("regular_task_run_items")

    if _index_exists("ix_regular_task_runs_started_at"):
        op.drop_index("ix_regular_task_runs_started_at", table_name="regular_task_runs")
    if _table_exists("regular_task_runs"):
        op.drop_table("regular_task_runs")

    # regular_tasks НЕ трогаем в downgrade, потому что она могла существовать до этой миграции
    # (иначе рискуем снести чужие данные/таблицу).
