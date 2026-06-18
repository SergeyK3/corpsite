"""ADR-038 Phase D.3 — HR sync audit log (export/preview/apply history).

Revision ID: m6f7a8b9c0d1
Revises: l5e6f7a8b9c0
Create Date: 2026-06-18
"""
from __future__ import annotations

from alembic import op

revision = "m6f7a8b9c0d1"
down_revision = "l5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_sync_audit_log (
            sync_audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            happened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actor_user_id BIGINT NULL
                REFERENCES public.users(user_id) ON DELETE SET NULL,
            actor_login TEXT NULL,
            operation TEXT NOT NULL,
            dry_run BOOLEAN NOT NULL DEFAULT FALSE,
            package_name TEXT NULL,
            validation_ok BOOLEAN NULL,
            notes TEXT NULL,
            summary JSONB NOT NULL DEFAULT '{}'::jsonb,
            context JSONB NOT NULL DEFAULT '{}'::jsonb,
            warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
            errors JSONB NOT NULL DEFAULT '[]'::jsonb,
            CONSTRAINT ck_hr_sync_audit_log_operation
                CHECK (operation IN ('export', 'preview', 'apply'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_sync_audit_log_happened_at
            ON public.hr_sync_audit_log (happened_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_sync_audit_log_operation
            ON public.hr_sync_audit_log (operation, happened_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.hr_sync_audit_log CASCADE")
