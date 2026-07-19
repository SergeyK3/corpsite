"""HR Baseline + PublicationOrigin — replace canonical snapshot lifecycle.

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f7
"""
from __future__ import annotations

from alembic import op

revision = "b3c4d5e6f7a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- PublicationOrigin (immutable provenance) ---
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_publication_origins (
            publication_origin_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            report_period DATE NOT NULL,
            published_at TIMESTAMPTZ NOT NULL,
            published_by BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            source_import_code TEXT NULL,
            baseline_id BIGINT NULL,
            batch_id BIGINT NULL
                REFERENCES public.hr_import_batches (batch_id) ON DELETE SET NULL,
            entry_count INT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hr_publication_origins_report_period
            ON public.hr_publication_origins (report_period, published_at DESC)
        """
    )

    # --- Rename canonical snapshot tables → baseline ---
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.hr_canonical_snapshots') IS NOT NULL
               AND to_regclass('public.hr_control_list_baselines') IS NULL THEN
                ALTER TABLE public.hr_canonical_snapshots
                    RENAME TO hr_control_list_baselines;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.hr_canonical_snapshot_entries') IS NOT NULL
               AND to_regclass('public.hr_baseline_entries') IS NULL THEN
                ALTER TABLE public.hr_canonical_snapshot_entries
                    RENAME TO hr_baseline_entries;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'hr_control_list_baselines'
                  AND column_name = 'snapshot_id'
            ) THEN
                ALTER TABLE public.hr_control_list_baselines
                    RENAME COLUMN snapshot_id TO baseline_id;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'hr_baseline_entries'
                  AND column_name = 'snapshot_id'
            ) THEN
                ALTER TABLE public.hr_baseline_entries
                    RENAME COLUMN snapshot_id TO baseline_id;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'hr_baseline_entries'
                  AND column_name = 'payload'
            ) THEN
                ALTER TABLE public.hr_baseline_entries
                    RENAME COLUMN payload TO effective_payload;
            END IF;
        END $$
        """
    )

    # --- Baseline columns ---
    op.execute(
        """
        ALTER TABLE public.hr_control_list_baselines
            ADD COLUMN IF NOT EXISTS publication_origin_id BIGINT NULL
                REFERENCES public.hr_publication_origins (publication_origin_id),
            ADD COLUMN IF NOT EXISTS report_period DATE NULL,
            ADD COLUMN IF NOT EXISTS publication_notes TEXT NULL,
            ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS deleted_by BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS deletion_reason TEXT NULL
        """
    )

    # Relax batch coupling: baseline survives batch delete
    op.execute(
        """
        DO $$
        DECLARE
            con record;
        BEGIN
            FOR con IN
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = 'hr_control_list_baselines'
                  AND c.contype = 'f'
                  AND pg_get_constraintdef(c.oid) LIKE '%source_batch_id%'
                  AND pg_get_constraintdef(c.oid) LIKE '%CASCADE%'
            LOOP
                EXECUTE format(
                    'ALTER TABLE public.hr_control_list_baselines DROP CONSTRAINT %I',
                    con.conname
                );
            END LOOP;
        END $$
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_control_list_baselines
            ALTER COLUMN source_batch_id DROP NOT NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_hclb_source_batch_id'
            ) THEN
                ALTER TABLE public.hr_control_list_baselines
                    ADD CONSTRAINT fk_hclb_source_batch_id
                    FOREIGN KEY (source_batch_id)
                    REFERENCES public.hr_import_batches (batch_id)
                    ON DELETE SET NULL;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_hr_canonical_snapshots_source_batch'
            ) THEN
                ALTER TABLE public.hr_control_list_baselines
                    DROP CONSTRAINT uq_hr_canonical_snapshots_source_batch;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DROP INDEX IF EXISTS public.uq_hr_canonical_snapshots_active_source_type
        """
    )

    # Drop legacy version/status constraints and columns
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_hr_canonical_snapshots_status'
            ) THEN
                ALTER TABLE public.hr_control_list_baselines
                    DROP CONSTRAINT chk_hr_canonical_snapshots_status;
            END IF;
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_hr_canonical_snapshots_version_positive'
            ) THEN
                ALTER TABLE public.hr_control_list_baselines
                    DROP CONSTRAINT chk_hr_canonical_snapshots_version_positive;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_control_list_baselines
            DROP COLUMN IF EXISTS version,
            DROP COLUMN IF EXISTS status,
            DROP COLUMN IF EXISTS superseded_by_snapshot_id,
            DROP COLUMN IF EXISTS superseded_at
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hclb_period_published_active
            ON public.hr_control_list_baselines (report_period, promoted_at DESC)
            WHERE deleted_at IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hclb_soft_deleted
            ON public.hr_control_list_baselines (deleted_at)
            WHERE deleted_at IS NOT NULL
        """
    )

    # --- Deletion audit ---
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_baseline_deletion_log (
            deletion_log_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            baseline_id BIGINT NOT NULL,
            publication_origin_id BIGINT NOT NULL
                REFERENCES public.hr_publication_origins (publication_origin_id),
            deletion_kind TEXT NOT NULL CHECK (deletion_kind IN ('SOFT', 'HARD')),
            report_period DATE NOT NULL,
            published_at TIMESTAMPTZ NOT NULL,
            published_by BIGINT NOT NULL,
            source_import_code TEXT NULL,
            entry_count INT NULL,
            deleted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_by BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            deletion_reason TEXT NULL,
            restored_at TIMESTAMPTZ NULL,
            restored_by BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL
        )
        """
    )

    # --- Backfill report_period + publication origins from legacy snapshots ---
    op.execute(
        """
        UPDATE public.hr_control_list_baselines bl
        SET report_period = COALESCE(
            bl.report_period,
            sf.report_month,
            date_trunc('month', bl.promoted_at)::date
        )
        FROM public.hr_import_batches b
        LEFT JOIN public.hr_source_files sf ON sf.source_file_id = b.source_file_id
        WHERE bl.source_batch_id = b.batch_id
          AND bl.report_period IS NULL
        """
    )
    op.execute(
        """
        UPDATE public.hr_control_list_baselines
        SET report_period = date_trunc('month', promoted_at)::date
        WHERE report_period IS NULL
        """
    )
    op.execute(
        """
        INSERT INTO public.hr_publication_origins (
            report_period,
            published_at,
            published_by,
            source_import_code,
            baseline_id,
            batch_id,
            entry_count
        )
        SELECT
            bl.report_period,
            bl.promoted_at,
            bl.promoted_by,
            b.import_code,
            bl.baseline_id,
            bl.source_batch_id,
            bl.entry_count
        FROM public.hr_control_list_baselines bl
        LEFT JOIN public.hr_import_batches b ON b.batch_id = bl.source_batch_id
        WHERE bl.publication_origin_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE public.hr_control_list_baselines bl
        SET publication_origin_id = po.publication_origin_id
        FROM public.hr_publication_origins po
        WHERE po.baseline_id = bl.baseline_id
          AND bl.publication_origin_id IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_control_list_baselines
            ALTER COLUMN report_period SET NOT NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_hclb_publication_origin_id'
            ) THEN
                ALTER TABLE public.hr_control_list_baselines
                    ADD CONSTRAINT fk_hclb_publication_origin_id
                    FOREIGN KEY (publication_origin_id)
                    REFERENCES public.hr_publication_origins (publication_origin_id)
                    ON DELETE RESTRICT;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_publication_origins
            ADD CONSTRAINT fk_hpo_baseline_id
            FOREIGN KEY (baseline_id)
            REFERENCES public.hr_control_list_baselines (baseline_id)
            ON DELETE SET NULL
        """
    )

    # --- Batch diff lifecycle columns ---
    op.execute(
        """
        ALTER TABLE public.hr_import_batches
            ADD COLUMN IF NOT EXISTS comparison_baseline_id BIGINT NULL
                REFERENCES public.hr_control_list_baselines (baseline_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS comparison_publication_origin_id BIGINT NULL
                REFERENCES public.hr_publication_origins (publication_origin_id),
            ADD COLUMN IF NOT EXISTS diff_status TEXT NOT NULL DEFAULT 'NOT_COMPUTED',
            ADD COLUMN IF NOT EXISTS diff_computed_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_hr_import_batches_diff_status'
            ) THEN
                ALTER TABLE public.hr_import_batches
                    ADD CONSTRAINT chk_hr_import_batches_diff_status
                    CHECK (diff_status IN ('NOT_COMPUTED', 'STALE', 'CURRENT'));
            END IF;
        END $$
        """
    )

    # --- Personnel provenance ---
    op.execute(
        """
        ALTER TABLE public.employee_documents
            ADD COLUMN IF NOT EXISTS publication_origin_id BIGINT NULL
                REFERENCES public.hr_publication_origins (publication_origin_id),
            ADD COLUMN IF NOT EXISTS baseline_id BIGINT NULL
                REFERENCES public.hr_control_list_baselines (baseline_id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        UPDATE public.employee_documents ed
        SET baseline_id = bl.baseline_id,
            publication_origin_id = bl.publication_origin_id
        FROM public.hr_control_list_baselines bl
        WHERE ed.source_batch_id IS NOT NULL
          AND bl.source_batch_id = ed.source_batch_id
          AND ed.publication_origin_id IS NULL
        """
    )

    # diff_removals: CASCADE on baseline delete → SET NULL (protect batch rows)
    op.execute(
        """
        DO $$
        DECLARE
            con record;
        BEGIN
            FOR con IN
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = 'hr_import_diff_removals'
                  AND c.contype = 'f'
                  AND pg_get_constraintdef(c.oid) LIKE '%canonical_snapshot_id%'
            LOOP
                EXECUTE format(
                    'ALTER TABLE public.hr_import_diff_removals DROP CONSTRAINT %I',
                    con.conname
                );
            END LOOP;
        END $$
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_import_diff_removals
            ADD COLUMN IF NOT EXISTS comparison_baseline_id BIGINT NULL
                REFERENCES public.hr_control_list_baselines (baseline_id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        UPDATE public.hr_import_diff_removals
        SET comparison_baseline_id = canonical_snapshot_id
        WHERE comparison_baseline_id IS NULL
          AND canonical_snapshot_id IS NOT NULL
        """
    )

    # hr_change_events: CASCADE → SET NULL for hard baseline delete safety
    op.execute(
        """
        DO $$
        DECLARE
            con record;
        BEGIN
            FOR con IN
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = 'hr_change_events'
                  AND c.contype = 'f'
                  AND (
                    pg_get_constraintdef(c.oid) LIKE '%prior_snapshot_id%'
                    OR pg_get_constraintdef(c.oid) LIKE '%new_snapshot_id%'
                  )
            LOOP
                EXECUTE format(
                    'ALTER TABLE public.hr_change_events DROP CONSTRAINT %I',
                    con.conname
                );
            END LOOP;
        END $$
        """
    )
    op.execute(
        """
        ALTER TABLE public.hr_change_events
            ADD COLUMN IF NOT EXISTS prior_baseline_id BIGINT NULL
                REFERENCES public.hr_control_list_baselines (baseline_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS new_baseline_id BIGINT NULL
                REFERENCES public.hr_control_list_baselines (baseline_id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS prior_publication_origin_id BIGINT NULL
                REFERENCES public.hr_publication_origins (publication_origin_id),
            ADD COLUMN IF NOT EXISTS new_publication_origin_id BIGINT NULL
                REFERENCES public.hr_publication_origins (publication_origin_id)
        """
    )
    op.execute(
        """
        UPDATE public.hr_change_events
        SET prior_baseline_id = prior_snapshot_id,
            new_baseline_id = new_snapshot_id
        WHERE prior_baseline_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE public.hr_change_events ce
        SET prior_publication_origin_id = po.publication_origin_id
        FROM public.hr_control_list_baselines bl
        JOIN public.hr_publication_origins po ON po.baseline_id = bl.baseline_id
        WHERE ce.prior_baseline_id = bl.baseline_id
          AND ce.prior_publication_origin_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE public.hr_change_events ce
        SET new_publication_origin_id = po.publication_origin_id
        FROM public.hr_control_list_baselines bl
        JOIN public.hr_publication_origins po ON po.baseline_id = bl.baseline_id
        WHERE ce.new_baseline_id = bl.baseline_id
          AND ce.new_publication_origin_id IS NULL
        """
    )

    # Compatibility views for legacy table names (read-only SQL in old code paths)
    op.execute(
        """
        CREATE OR REPLACE VIEW public.hr_canonical_snapshots AS
        SELECT
            bl.baseline_id AS snapshot_id,
            bl.source_batch_id,
            bl.source_type,
            bl.entry_count,
            bl.promoted_by,
            bl.promoted_at,
            bl.publication_origin_id,
            bl.report_period,
            bl.deleted_at
        FROM public.hr_control_list_baselines bl
        WHERE bl.deleted_at IS NULL
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW public.hr_canonical_snapshot_entries AS
        SELECT
            e.entry_id,
            e.baseline_id AS snapshot_id,
            e.entity_scope,
            e.record_kind,
            e.match_key,
            e.canonical_hash,
            e.employee_id,
            e.iin,
            e.effective_payload AS payload,
            e.source_row_id,
            e.source_normalized_record_id
        FROM public.hr_baseline_entries e
        JOIN public.hr_control_list_baselines bl ON bl.baseline_id = e.baseline_id
        WHERE bl.deleted_at IS NULL
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.hr_control_list_baselines IS
            'Approved control-list baseline (clean copy). Effective per period = MAX(published_at) where deleted_at IS NULL.';
        COMMENT ON TABLE public.hr_publication_origins IS
            'Immutable publication provenance for baseline and promoted personnel data.';
        COMMENT ON TABLE public.hr_baseline_deletion_log IS
            'Audit of soft/hard baseline deletion; baseline payload is not retained after hard delete.';
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public.hr_canonical_snapshot_entries")
    op.execute("DROP VIEW IF EXISTS public.hr_canonical_snapshots")
    op.execute("DROP TABLE IF EXISTS public.hr_baseline_deletion_log")
    op.execute(
        """
        ALTER TABLE public.hr_import_batches
            DROP COLUMN IF EXISTS comparison_baseline_id,
            DROP COLUMN IF EXISTS comparison_publication_origin_id,
            DROP COLUMN IF EXISTS diff_status,
            DROP COLUMN IF EXISTS diff_computed_at
        """
    )
    op.execute(
        """
        ALTER TABLE public.employee_documents
            DROP COLUMN IF EXISTS publication_origin_id,
            DROP COLUMN IF EXISTS baseline_id
        """
    )
    op.execute("DROP TABLE IF EXISTS public.hr_publication_origins CASCADE")
