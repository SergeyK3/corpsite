"""ADR-043 Phase C3 — personnel lifecycle run journal.

Revision ID: y7z8a9b0c1d2
Revises: x6y7z8a9b0c1
"""
from __future__ import annotations

from alembic import op

revision = "y7z8a9b0c1d2"
down_revision = "x6y7z8a9b0c1"
branch_labels = None
depends_on = None

_LIFECYCLE_RUN_STATUSES = ("running", "completed", "failed", "cancelled")


def upgrade() -> None:
    statuses = ", ".join(f"'{s}'" for s in _LIFECYCLE_RUN_STATUSES)
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.hr_personnel_lifecycle_runs (
            run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            previous_snapshot_id BIGINT NOT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE RESTRICT,
            snapshot_id BIGINT NOT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE RESTRICT,
            status TEXT NOT NULL DEFAULT 'running',
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ NULL,
            actor_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            dry_run BOOLEAN NOT NULL DEFAULT TRUE,
            refresh_cache BOOLEAN NOT NULL DEFAULT TRUE,
            enqueue BOOLEAN NOT NULL DEFAULT FALSE,
            sync_persons BOOLEAN NOT NULL DEFAULT FALSE,
            effective_entries_processed INTEGER NOT NULL DEFAULT 0,
            events_created INTEGER NOT NULL DEFAULT 0,
            events_existing INTEGER NOT NULL DEFAULT 0,
            enrollment_created INTEGER NOT NULL DEFAULT 0,
            enrollment_existing INTEGER NOT NULL DEFAULT 0,
            persons_created INTEGER NOT NULL DEFAULT 0,
            persons_updated INTEGER NOT NULL DEFAULT 0,
            assignments_created INTEGER NOT NULL DEFAULT 0,
            assignments_updated INTEGER NOT NULL DEFAULT 0,
            assignments_closed INTEGER NOT NULL DEFAULT 0,
            warnings_count INTEGER NOT NULL DEFAULT 0,
            errors_count INTEGER NOT NULL DEFAULT 0,
            summary JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            CONSTRAINT chk_hplr_status CHECK (status IN ({statuses})),
            CONSTRAINT chk_hplr_snapshot_pair CHECK (previous_snapshot_id <> snapshot_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hplr_snapshot_pair
            ON public.hr_personnel_lifecycle_runs (previous_snapshot_id, snapshot_id, started_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hplr_status_started
            ON public.hr_personnel_lifecycle_runs (status, started_at DESC)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.hr_personnel_lifecycle_runs IS
            'ADR-043 C3: orchestrated monthly personnel lifecycle run journal.';
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.hr_personnel_lifecycle_runs CASCADE")
