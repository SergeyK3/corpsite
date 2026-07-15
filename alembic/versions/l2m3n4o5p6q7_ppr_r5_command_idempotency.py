"""PPR R5 — command_id idempotency store for application write path.

Additive table; no backfill. Safe downgrade drops table only.

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
"""
from __future__ import annotations

from alembic import op

revision = "l2m3n4o5p6q7"
down_revision = "k1l2m3n4o5p6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.ppr_command_executions (
            command_id TEXT NOT NULL PRIMARY KEY,
            command_type TEXT NOT NULL,
            person_id BIGINT NOT NULL REFERENCES public.persons(person_id),
            request_fingerprint TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            result_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ NULL,
            CONSTRAINT chk_ppr_command_executions_status
                CHECK (status IN ('pending', 'completed'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ppr_command_executions_person_id
            ON public.ppr_command_executions (person_id)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.ppr_command_executions IS
            'PPR R5 command_id idempotency — one row per successful mutation command'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.ppr_command_executions")
