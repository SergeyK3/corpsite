"""ADR-040 Phase A — canonical HR snapshot schema.

Revision ID: q9r0s1t2u3v4
Revises: p8q9r0s1t2u3
"""
from __future__ import annotations

from alembic import op

revision = "q9r0s1t2u3v4"
down_revision = "p8q9r0s1t2u3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_canonical_snapshots (
            snapshot_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source_batch_id BIGINT NOT NULL
                REFERENCES public.hr_import_batches (batch_id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'HR_CONTROL_LIST',
            status TEXT NOT NULL DEFAULT 'active',
            entry_count INTEGER NOT NULL DEFAULT 0,
            promoted_by BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            promoted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            superseded_by_snapshot_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE SET NULL,
            superseded_at TIMESTAMPTZ NULL,

            CONSTRAINT chk_hr_canonical_snapshots_status
                CHECK (status IN ('active', 'superseded')),
            CONSTRAINT chk_hr_canonical_snapshots_version_positive
                CHECK (version > 0),
            CONSTRAINT chk_hr_canonical_snapshots_entry_count_nonneg
                CHECK (entry_count >= 0),
            CONSTRAINT uq_hr_canonical_snapshots_source_batch
                UNIQUE (source_batch_id)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hr_canonical_snapshots_active_source_type
            ON public.hr_canonical_snapshots (source_type)
            WHERE status = 'active'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_canonical_snapshots_status
            ON public.hr_canonical_snapshots (status)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_canonical_snapshot_entries (
            entry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            snapshot_id BIGINT NOT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE CASCADE,
            entity_scope TEXT NOT NULL,
            record_kind TEXT NOT NULL,
            match_key TEXT NOT NULL,
            canonical_hash TEXT NOT NULL,
            employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            iin TEXT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            source_row_id BIGINT NULL
                REFERENCES public.hr_import_rows (row_id) ON DELETE SET NULL,
            source_normalized_record_id BIGINT NULL
                REFERENCES public.hr_import_normalized_records (normalized_record_id)
                ON DELETE SET NULL,

            CONSTRAINT uq_hcs_entries_snapshot_match_key
                UNIQUE (snapshot_id, match_key),
            CONSTRAINT chk_hcs_entries_record_kind
                CHECK (record_kind IN (
                    'roster', 'training', 'certificate', 'category', 'education'
                )),
            CONSTRAINT chk_hcs_entries_canonical_hash_nonempty
                CHECK (length(trim(canonical_hash)) > 0),
            CONSTRAINT chk_hcs_entries_match_key_nonempty
                CHECK (length(trim(match_key)) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hcs_entries_snapshot_id
            ON public.hr_canonical_snapshot_entries (snapshot_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hcs_entries_canonical_hash
            ON public.hr_canonical_snapshot_entries (snapshot_id, canonical_hash)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hcs_entries_employee_id
            ON public.hr_canonical_snapshot_entries (snapshot_id, employee_id)
            WHERE employee_id IS NOT NULL
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.hr_canonical_snapshots IS
            'ADR-040: versioned canonical HR import snapshot after review/promotion.';
        COMMENT ON TABLE public.hr_canonical_snapshot_entries IS
            'ADR-040: materialized effective import records for monthly diff baseline.';
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.hr_canonical_snapshot_entries CASCADE")
    op.execute("DROP TABLE IF EXISTS public.hr_canonical_snapshots CASCADE")
