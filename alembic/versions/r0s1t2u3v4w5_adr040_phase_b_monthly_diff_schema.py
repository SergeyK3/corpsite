"""ADR-040 Phase B — monthly diff columns and REMOVED entry storage.

Revision ID: r0s1t2u3v4w5
Revises: q9r0s1t2u3v4
"""
from __future__ import annotations

from alembic import op

revision = "r0s1t2u3v4w5"
down_revision = "q9r0s1t2u3v4"
branch_labels = None
depends_on = None

_DIFF_STATUS_CHECK = """
    diff_status IS NULL OR diff_status IN (
        'UNCHANGED', 'NEW', 'CHANGED', 'REMOVED', 'CONFLICT'
    )
"""


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE public.hr_import_rows
            ADD COLUMN IF NOT EXISTS diff_status TEXT NULL,
            ADD COLUMN IF NOT EXISTS canonical_snapshot_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS canonical_entry_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshot_entries (entry_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS canonical_hash TEXT NULL,
            ADD COLUMN IF NOT EXISTS field_diffs JSONB NULL,
            ADD COLUMN IF NOT EXISTS diff_computed_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_hr_import_rows_diff_status'
            ) THEN
                ALTER TABLE public.hr_import_rows
                    ADD CONSTRAINT chk_hr_import_rows_diff_status
                        CHECK ({_DIFF_STATUS_CHECK});
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_rows_batch_diff_status
            ON public.hr_import_rows (batch_id, diff_status)
            WHERE diff_status IS NOT NULL
        """
    )

    op.execute(
        f"""
        ALTER TABLE public.hr_import_normalized_records
            ADD COLUMN IF NOT EXISTS diff_status TEXT NULL,
            ADD COLUMN IF NOT EXISTS canonical_snapshot_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS canonical_entry_id BIGINT NULL
                REFERENCES public.hr_canonical_snapshot_entries (entry_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS canonical_hash TEXT NULL,
            ADD COLUMN IF NOT EXISTS field_diffs JSONB NULL,
            ADD COLUMN IF NOT EXISTS diff_computed_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_hinr_diff_status'
            ) THEN
                ALTER TABLE public.hr_import_normalized_records
                    ADD CONSTRAINT chk_hinr_diff_status
                        CHECK ({_DIFF_STATUS_CHECK});
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hinr_batch_diff_status
            ON public.hr_import_normalized_records (batch_id, diff_status)
            WHERE diff_status IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_import_diff_removals (
            removal_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            batch_id BIGINT NOT NULL
                REFERENCES public.hr_import_batches (batch_id) ON DELETE CASCADE,
            canonical_snapshot_id BIGINT NOT NULL
                REFERENCES public.hr_canonical_snapshots (snapshot_id) ON DELETE CASCADE,
            canonical_entry_id BIGINT NOT NULL
                REFERENCES public.hr_canonical_snapshot_entries (entry_id) ON DELETE CASCADE,
            match_key TEXT NOT NULL,
            record_kind TEXT NOT NULL,
            canonical_hash TEXT NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            diff_status TEXT NOT NULL DEFAULT 'REMOVED',
            diff_computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT uq_hr_import_diff_removals_batch_entry
                UNIQUE (batch_id, canonical_entry_id),
            CONSTRAINT chk_hr_import_diff_removals_status
                CHECK (diff_status = 'REMOVED'),
            CONSTRAINT chk_hr_import_diff_removals_record_kind
                CHECK (record_kind IN (
                    'roster', 'training', 'certificate', 'category', 'education'
                ))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_import_diff_removals_batch_id
            ON public.hr_import_diff_removals (batch_id)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.hr_import_diff_removals IS
            'ADR-040 Phase B: canonical snapshot entries absent from a new import batch.';
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.hr_import_diff_removals CASCADE")
    op.execute(
        """
        ALTER TABLE public.hr_import_normalized_records
            DROP CONSTRAINT IF EXISTS chk_hinr_diff_status,
            DROP COLUMN IF EXISTS diff_computed_at,
            DROP COLUMN IF EXISTS field_diffs,
            DROP COLUMN IF EXISTS canonical_hash,
            DROP COLUMN IF EXISTS canonical_entry_id,
            DROP COLUMN IF EXISTS canonical_snapshot_id,
            DROP COLUMN IF EXISTS diff_status
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_import_rows
            DROP CONSTRAINT IF EXISTS chk_hr_import_rows_diff_status,
            DROP COLUMN IF EXISTS diff_computed_at,
            DROP COLUMN IF EXISTS field_diffs,
            DROP COLUMN IF EXISTS canonical_hash,
            DROP COLUMN IF EXISTS canonical_entry_id,
            DROP COLUMN IF EXISTS canonical_snapshot_id,
            DROP COLUMN IF EXISTS diff_status
        """
    )
