"""WP-CL-012: control list apply execution journal schema.

Revision ID: z5a6b7c8d9e0f1
Revises: y4z5a6b7c8d9e0
Create Date: 2026-07-18 00:10:00.000000

Persistent apply execution state + idempotency journal.
No canonical PPR/Employment mutations in this migration.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "z5a6b7c8d9e0f1"
down_revision: Union[str, Sequence[str], None] = "y4z5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RUN_STATUSES = ("pending", "running", "succeeded", "partially_succeeded", "failed", "cancelled")
_ACTION_STATUSES = ("pending", "running", "succeeded", "skipped", "deferred", "failed")


def _sql_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    run_statuses_sql = _sql_tuple(_RUN_STATUSES)
    action_statuses_sql = _sql_tuple(_ACTION_STATUSES)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.control_list_apply_runs (
            apply_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            import_run_id BIGINT NOT NULL,
            review_run_key TEXT NOT NULL,
            plan_key TEXT NOT NULL,
            plan_fingerprint TEXT NOT NULL,
            plan_snapshot JSONB NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            requested_by_user_id BIGINT NULL,
            started_at TIMESTAMPTZ NULL,
            completed_at TIMESTAMPTZ NULL,
            failed_at TIMESTAMPTZ NULL,
            failure_code TEXT NULL,
            failure_message TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_control_list_apply_runs_import_run
                FOREIGN KEY (import_run_id)
                REFERENCES public.control_list_import_runs(import_run_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_control_list_apply_runs_requested_by
                FOREIGN KEY (requested_by_user_id)
                REFERENCES public.users(user_id)
                ON DELETE SET NULL,
            CONSTRAINT chk_control_list_apply_runs_review_run_key_nonempty
                CHECK (length(trim(review_run_key)) > 0),
            CONSTRAINT chk_control_list_apply_runs_plan_key_nonempty
                CHECK (length(trim(plan_key)) > 0),
            CONSTRAINT chk_control_list_apply_runs_plan_fingerprint_format
                CHECK (
                    length(plan_fingerprint) = 64
                    AND plan_fingerprint ~ '^[0-9a-f]{{64}}$'
                ),
            CONSTRAINT chk_control_list_apply_runs_status
                CHECK (status IN ({run_statuses_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_control_list_apply_runs_plan_fingerprint
            ON public.control_list_apply_runs (plan_fingerprint)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_apply_runs_import_run
            ON public.control_list_apply_runs (import_run_id, created_at DESC)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_apply_runs_status
            ON public.control_list_apply_runs (status, created_at DESC)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.control_list_apply_actions (
            apply_action_execution_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            apply_run_id BIGINT NOT NULL,
            action_index INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            target_aggregate TEXT NOT NULL,
            source_reference TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            action_fingerprint TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            started_at TIMESTAMPTZ NULL,
            completed_at TIMESTAMPTZ NULL,
            error_code TEXT NULL,
            error_message TEXT NULL,
            result_payload JSONB NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_control_list_apply_actions_apply_run
                FOREIGN KEY (apply_run_id)
                REFERENCES public.control_list_apply_runs(apply_run_id)
                ON DELETE CASCADE,
            CONSTRAINT uq_control_list_apply_actions_run_index
                UNIQUE (apply_run_id, action_index),
            CONSTRAINT uq_control_list_apply_actions_idempotency_key
                UNIQUE (idempotency_key),
            CONSTRAINT chk_control_list_apply_actions_action_index
                CHECK (action_index >= 0),
            CONSTRAINT chk_control_list_apply_actions_attempt_count
                CHECK (attempt_count >= 0),
            CONSTRAINT chk_control_list_apply_actions_status
                CHECK (status IN ({action_statuses_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_apply_actions_run
            ON public.control_list_apply_actions (apply_run_id, action_index)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_list_apply_actions_status
            ON public.control_list_apply_actions (status, updated_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.control_list_apply_actions")
    op.execute("DROP TABLE IF EXISTS public.control_list_apply_runs")
