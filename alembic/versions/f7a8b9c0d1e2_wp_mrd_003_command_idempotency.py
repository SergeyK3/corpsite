"""WP-MRD-003 — command_id idempotency store + CREATE version event type.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
"""
from __future__ import annotations

from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_mrd_command_executions (
            command_id TEXT NOT NULL PRIMARY KEY,
            command_type TEXT NOT NULL,
            performed_by BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            request_fingerprint TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            result_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ NULL,

            CONSTRAINT chk_hmce_status
                CHECK (status IN ('pending', 'completed')),
            CONSTRAINT chk_hmce_command_type
                CHECK (command_type IN ('FORK_VERSION', 'FORK_PERIOD'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hmce_performed_by
            ON public.hr_mrd_command_executions (performed_by, created_at DESC)
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_reference_version_events
            DROP CONSTRAINT IF EXISTS chk_hrve_event_type
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_reference_version_events
            ADD CONSTRAINT chk_hrve_event_type
                CHECK (event_type IN (
                    'FORK_VERSION', 'FORK_PERIOD', 'CLOSE', 'ACTIVATE', 'CREATE'
                ))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.hr_reference_version_events
            DROP CONSTRAINT IF EXISTS chk_hrve_event_type
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_reference_version_events
            ADD CONSTRAINT chk_hrve_event_type
                CHECK (event_type IN ('FORK_VERSION', 'FORK_PERIOD', 'CLOSE', 'ACTIVATE'))
        """
    )
    op.execute("DROP TABLE IF EXISTS public.hr_mrd_command_executions")
