"""WP-MRD-001 — Monthly Reference Dataset schema foundation (ADR-058).

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
"""
from __future__ import annotations

from alembic import op

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None

_SEED_ORIGIN_TYPES = (
    ("IMPORT_COMPARE", "Import comparison", "Difference detected by automatic import vs MRD comparison"),
    ("MANUAL_EDIT", "Manual edit", "Difference from operator manual correction in HR UI"),
    ("SYSTEM_RECALC", "System recalculation", "Difference after automatic recalculation or canonical migration"),
    ("MRD_FORK", "MRD fork", "Difference related to fork-version or fork-period orchestration"),
    ("DATA_REPAIR", "Data repair", "Difference created during migration or repair script"),
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Difference Origin registry (extensible, not a DB enum)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_difference_origin_types (
            origin_code TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            description TEXT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT chk_hdot_origin_code_nonempty
                CHECK (length(trim(origin_code)) > 0),
            CONSTRAINT chk_hdot_label_nonempty
                CHECK (length(trim(label)) > 0)
        )
        """
    )
    for code, label, description in _SEED_ORIGIN_TYPES:
        op.execute(
            f"""
            INSERT INTO public.hr_difference_origin_types (
                origin_code, label, description, is_active
            )
            VALUES (
                '{code}', '{label}', '{description.replace("'", "''")}', TRUE
            )
            ON CONFLICT (origin_code) DO NOTHING
            """
        )

    # ------------------------------------------------------------------
    # 2. MRD version container
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_monthly_references (
            mrd_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            report_period DATE NOT NULL,
            version INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            source_type TEXT NOT NULL DEFAULT 'HR_CONTROL_LIST',
            forked_from_reference_id BIGINT NULL,
            entry_count INTEGER NOT NULL DEFAULT 0,
            created_by BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            closed_at TIMESTAMPTZ NULL,
            closed_by BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            notes TEXT NULL,
            row_version INTEGER NOT NULL DEFAULT 1,

            CONSTRAINT chk_hmr_version_positive
                CHECK (version > 0),
            CONSTRAINT chk_hmr_status
                CHECK (status IN ('ACTIVE', 'CLOSED')),
            CONSTRAINT chk_hmr_entry_count_nonneg
                CHECK (entry_count >= 0),
            CONSTRAINT chk_hmr_row_version_positive
                CHECK (row_version > 0),
            CONSTRAINT chk_hmr_closed_consistency
                CHECK (
                    (status = 'CLOSED' AND closed_at IS NOT NULL)
                    OR (status = 'ACTIVE' AND closed_at IS NULL)
                ),
            CONSTRAINT uq_hmr_report_period_version
                UNIQUE (report_period, version)
        )
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_hmr_forked_from_reference_id'
            ) THEN
                ALTER TABLE public.hr_monthly_references
                    ADD CONSTRAINT fk_hmr_forked_from_reference_id
                    FOREIGN KEY (forked_from_reference_id)
                    REFERENCES public.hr_monthly_references (mrd_id)
                    ON DELETE RESTRICT;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hmr_one_active_per_period
            ON public.hr_monthly_references (report_period)
            WHERE status = 'ACTIVE'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hmr_report_period_status
            ON public.hr_monthly_references (report_period, status, version DESC)
        """
    )

    # ------------------------------------------------------------------
    # 3. Comparison run audit (IMPORT_COMPARE producer metadata)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_comparison_runs (
            comparison_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            batch_id BIGINT NULL
                REFERENCES public.hr_import_batches (batch_id) ON DELETE SET NULL,
            mrd_id BIGINT NOT NULL
                REFERENCES public.hr_monthly_references (mrd_id) ON DELETE RESTRICT,
            report_period DATE NOT NULL,
            status TEXT NOT NULL DEFAULT 'RUNNING',
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ NULL,
            started_by BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            stats JSONB NOT NULL DEFAULT '{}'::jsonb,

            CONSTRAINT chk_hcr_status
                CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hcr_batch_started
            ON public.hr_comparison_runs (batch_id, started_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hcr_mrd_started
            ON public.hr_comparison_runs (mrd_id, started_at DESC)
        """
    )

    # ------------------------------------------------------------------
    # 4. Detected Difference (persistent process entity)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_detected_differences (
            difference_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            report_period DATE NOT NULL,
            mrd_id BIGINT NOT NULL
                REFERENCES public.hr_monthly_references (mrd_id) ON DELETE RESTRICT,
            logical_key TEXT NOT NULL,
            entity_scope TEXT NOT NULL,
            record_kind TEXT NULL,
            attribute TEXT NOT NULL,
            business_type TEXT NOT NULL,
            lifecycle_status TEXT NOT NULL DEFAULT 'DETECTED',
            technical_diff_class TEXT NULL,
            difference_origin_code TEXT NOT NULL
                REFERENCES public.hr_difference_origin_types (origin_code) ON DELETE RESTRICT,
            origin_context JSONB NOT NULL DEFAULT '{}'::jsonb,
            old_value JSONB NULL,
            new_value JSONB NULL,
            supersedes_difference_id BIGINT NULL,
            last_comparison_run_id BIGINT NULL
                REFERENCES public.hr_comparison_runs (comparison_run_id) ON DELETE SET NULL,
            detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            confirmed_at TIMESTAMPTZ NULL,
            confirmed_by BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            rejected_at TIMESTAMPTZ NULL,
            rejected_by BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            reject_basis TEXT NULL,
            row_version INTEGER NOT NULL DEFAULT 1,

            CONSTRAINT chk_hdd_logical_key_nonempty
                CHECK (length(trim(logical_key)) > 0),
            CONSTRAINT chk_hdd_attribute_nonempty
                CHECK (length(trim(attribute)) > 0),
            CONSTRAINT chk_hdd_business_type
                CHECK (business_type IN ('NEVER_CONFIRMED', 'PERIOD_CHANGED')),
            CONSTRAINT chk_hdd_lifecycle_status
                CHECK (lifecycle_status IN ('DETECTED', 'CONFIRMED', 'REJECTED', 'SUPERSEDED')),
            CONSTRAINT chk_hdd_technical_diff_class
                CHECK (
                    technical_diff_class IS NULL
                    OR technical_diff_class IN ('NEW', 'CHANGED', 'REMOVED', 'CONFLICT')
                ),
            CONSTRAINT chk_hdd_row_version_positive
                CHECK (row_version > 0),
            CONSTRAINT chk_hdd_no_self_supersession
                CHECK (
                    supersedes_difference_id IS NULL
                    OR supersedes_difference_id <> difference_id
                ),
            CONSTRAINT chk_hdd_superseded_has_no_supersedes_link
                CHECK (
                    lifecycle_status <> 'SUPERSEDED'
                    OR supersedes_difference_id IS NULL
                ),
            CONSTRAINT chk_hdd_supersedes_only_on_detected
                CHECK (
                    supersedes_difference_id IS NULL
                    OR lifecycle_status = 'DETECTED'
                ),
            CONSTRAINT chk_hdd_origin_context_is_object
                CHECK (jsonb_typeof(origin_context) = 'object')
        )
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_hdd_supersedes_difference_id'
            ) THEN
                ALTER TABLE public.hr_detected_differences
                    ADD CONSTRAINT fk_hdd_supersedes_difference_id
                    FOREIGN KEY (supersedes_difference_id)
                    REFERENCES public.hr_detected_differences (difference_id)
                    ON DELETE RESTRICT;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hdd_one_open_detected_per_logical_key
            ON public.hr_detected_differences (report_period, mrd_id, logical_key)
            WHERE lifecycle_status = 'DETECTED'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hdd_queue_detected
            ON public.hr_detected_differences (report_period, lifecycle_status, detected_at DESC)
            WHERE lifecycle_status = 'DETECTED'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hdd_origin
            ON public.hr_detected_differences (difference_origin_code, lifecycle_status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hdd_supersedes
            ON public.hr_detected_differences (supersedes_difference_id)
            WHERE supersedes_difference_id IS NOT NULL
        """
    )

    # ------------------------------------------------------------------
    # 5. Confirmed Change event log (append-only)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_confirmed_changes (
            confirmed_change_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            detected_difference_id BIGINT NOT NULL
                REFERENCES public.hr_detected_differences (difference_id) ON DELETE RESTRICT,
            report_period DATE NOT NULL,
            mrd_id BIGINT NOT NULL
                REFERENCES public.hr_monthly_references (mrd_id) ON DELETE RESTRICT,
            entity_scope TEXT NOT NULL,
            attribute TEXT NOT NULL,
            old_value JSONB NULL,
            new_value JSONB NOT NULL,
            confirmed_by BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            confirmed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            basis TEXT NULL,
            difference_origin_code TEXT NOT NULL
                REFERENCES public.hr_difference_origin_types (origin_code) ON DELETE RESTRICT,
            origin_context JSONB NULL,
            source_batch_id BIGINT NULL
                REFERENCES public.hr_import_batches (batch_id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT uq_hcc_one_event_per_difference
                UNIQUE (detected_difference_id),
            CONSTRAINT chk_hcc_attribute_nonempty
                CHECK (length(trim(attribute)) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hcc_report_period_confirmed_at
            ON public.hr_confirmed_changes (report_period, confirmed_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hcc_mrd_confirmed_at
            ON public.hr_confirmed_changes (mrd_id, confirmed_at DESC)
        """
    )

    # ------------------------------------------------------------------
    # 6. MRD entries (confirmed state; mutable only in ACTIVE version)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_monthly_reference_entries (
            entry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            mrd_id BIGINT NOT NULL
                REFERENCES public.hr_monthly_references (mrd_id) ON DELETE RESTRICT,
            entity_scope TEXT NOT NULL,
            record_kind TEXT NOT NULL,
            match_key TEXT NOT NULL,
            canonical_hash TEXT NOT NULL,
            employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            iin TEXT NULL,
            effective_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            source_row_id BIGINT NULL
                REFERENCES public.hr_import_rows (row_id) ON DELETE SET NULL,
            source_normalized_record_id BIGINT NULL,
            last_confirmed_change_id BIGINT NULL
                REFERENCES public.hr_confirmed_changes (confirmed_change_id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            row_version INTEGER NOT NULL DEFAULT 1,

            CONSTRAINT uq_hmre_mrd_match_key
                UNIQUE (mrd_id, match_key),
            CONSTRAINT chk_hmre_record_kind
                CHECK (record_kind IN (
                    'roster', 'training', 'certificate', 'category', 'education'
                )),
            CONSTRAINT chk_hmre_canonical_hash_nonempty
                CHECK (length(trim(canonical_hash)) > 0),
            CONSTRAINT chk_hmre_match_key_nonempty
                CHECK (length(trim(match_key)) > 0),
            CONSTRAINT chk_hmre_row_version_positive
                CHECK (row_version > 0)
        )
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.hr_import_normalized_records') IS NOT NULL
               AND NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'fk_hmre_source_normalized_record_id'
               ) THEN
                ALTER TABLE public.hr_monthly_reference_entries
                    ADD CONSTRAINT fk_hmre_source_normalized_record_id
                    FOREIGN KEY (source_normalized_record_id)
                    REFERENCES public.hr_import_normalized_records (normalized_record_id)
                    ON DELETE SET NULL;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hmre_mrd_id
            ON public.hr_monthly_reference_entries (mrd_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hmre_canonical_hash
            ON public.hr_monthly_reference_entries (mrd_id, canonical_hash)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hmre_employee_id
            ON public.hr_monthly_reference_entries (mrd_id, employee_id)
            WHERE employee_id IS NOT NULL
        """
    )

    # ------------------------------------------------------------------
    # 7. Version events journal (fork / close / activate)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.hr_reference_version_events (
            event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            event_type TEXT NOT NULL,
            report_period DATE NOT NULL,
            mrd_id BIGINT NOT NULL
                REFERENCES public.hr_monthly_references (mrd_id) ON DELETE RESTRICT,
            source_mrd_id BIGINT NULL
                REFERENCES public.hr_monthly_references (mrd_id) ON DELETE RESTRICT,
            performed_by BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            event_context JSONB NOT NULL DEFAULT '{}'::jsonb,

            CONSTRAINT chk_hrve_event_type
                CHECK (event_type IN ('FORK_VERSION', 'FORK_PERIOD', 'CLOSE', 'ACTIVATE')),
            CONSTRAINT chk_hrve_event_context_is_object
                CHECK (jsonb_typeof(event_context) = 'object')
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hrve_mrd_performed_at
            ON public.hr_reference_version_events (mrd_id, performed_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_hrve_report_period_performed_at
            ON public.hr_reference_version_events (report_period, performed_at DESC)
        """
    )

    # ------------------------------------------------------------------
    # Invariant enforcement triggers
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.prevent_hr_confirmed_changes_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'hr_confirmed_changes is append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_hcc_append_only
            BEFORE UPDATE OR DELETE ON public.hr_confirmed_changes
            FOR EACH ROW
            EXECUTE FUNCTION public.prevent_hr_confirmed_changes_mutation();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.prevent_hr_detected_differences_delete()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'hr_detected_differences rows must not be deleted';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_hdd_no_delete
            BEFORE DELETE ON public.hr_detected_differences
            FOR EACH ROW
            EXECUTE FUNCTION public.prevent_hr_detected_differences_delete();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.enforce_hr_detected_differences_lifecycle()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                RETURN NEW;
            END IF;

            IF OLD.lifecycle_status IN ('CONFIRMED', 'REJECTED', 'SUPERSEDED')
               AND NEW.lifecycle_status IS DISTINCT FROM OLD.lifecycle_status THEN
                RAISE EXCEPTION
                    'hr_detected_differences lifecycle transition from % to % is forbidden',
                    OLD.lifecycle_status,
                    NEW.lifecycle_status;
            END IF;

            IF OLD.lifecycle_status = 'DETECTED'
               AND NEW.lifecycle_status NOT IN ('DETECTED', 'CONFIRMED', 'REJECTED', 'SUPERSEDED') THEN
                RAISE EXCEPTION 'invalid hr_detected_differences lifecycle status %', NEW.lifecycle_status;
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_hdd_lifecycle_transitions
            BEFORE UPDATE OF lifecycle_status ON public.hr_detected_differences
            FOR EACH ROW
            EXECUTE FUNCTION public.enforce_hr_detected_differences_lifecycle();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.prevent_hmr_closed_entry_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            parent_status TEXT;
        BEGIN
            SELECT status
            INTO parent_status
            FROM public.hr_monthly_references
            WHERE mrd_id = COALESCE(NEW.mrd_id, OLD.mrd_id);

            IF parent_status = 'CLOSED' THEN
                RAISE EXCEPTION
                    'hr_monthly_reference_entries are immutable when parent MRD is CLOSED';
            END IF;

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_hmre_closed_mrd_immutable
            BEFORE INSERT OR UPDATE OR DELETE ON public.hr_monthly_reference_entries
            FOR EACH ROW
            EXECUTE FUNCTION public.prevent_hmr_closed_entry_mutation();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.enforce_active_difference_origin()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            origin_active BOOLEAN;
        BEGIN
            SELECT is_active
            INTO origin_active
            FROM public.hr_difference_origin_types
            WHERE origin_code = NEW.difference_origin_code;

            IF origin_active IS DISTINCT FROM TRUE THEN
                RAISE EXCEPTION
                    'difference_origin_code % is missing or inactive',
                    NEW.difference_origin_code;
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_hdd_active_origin
            BEFORE INSERT OR UPDATE OF difference_origin_code
            ON public.hr_detected_differences
            FOR EACH ROW
            EXECUTE FUNCTION public.enforce_active_difference_origin();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_hcc_active_origin
            BEFORE INSERT OR UPDATE OF difference_origin_code
            ON public.hr_confirmed_changes
            FOR EACH ROW
            EXECUTE FUNCTION public.enforce_active_difference_origin();
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.hr_monthly_references IS
            'ADR-058: Monthly Reference Dataset (MRD) version container per report period.';
        COMMENT ON TABLE public.hr_monthly_reference_entries IS
            'ADR-058: confirmed MRD state entries; mutable only while parent MRD is ACTIVE.';
        COMMENT ON TABLE public.hr_difference_origin_types IS
            'ADR-058: extensible Difference Origin registry.';
        COMMENT ON TABLE public.hr_detected_differences IS
            'ADR-058: persistent Detected Difference with lifecycle and origin.';
        COMMENT ON TABLE public.hr_confirmed_changes IS
            'ADR-058: append-only Confirmed Change event log.';
        COMMENT ON TABLE public.hr_comparison_runs IS
            'ADR-058: Automatic Comparison run audit metadata.';
        COMMENT ON TABLE public.hr_reference_version_events IS
            'ADR-058: MRD fork/close/activate version event journal.';
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_hcc_active_origin ON public.hr_confirmed_changes"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_hdd_active_origin ON public.hr_detected_differences"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_hmre_closed_mrd_immutable ON public.hr_monthly_reference_entries"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_hdd_lifecycle_transitions ON public.hr_detected_differences"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_hdd_no_delete ON public.hr_detected_differences")
    op.execute("DROP TRIGGER IF EXISTS trg_hcc_append_only ON public.hr_confirmed_changes")

    op.execute("DROP FUNCTION IF EXISTS public.enforce_active_difference_origin()")
    op.execute("DROP FUNCTION IF EXISTS public.prevent_hmr_closed_entry_mutation()")
    op.execute("DROP FUNCTION IF EXISTS public.enforce_hr_detected_differences_lifecycle()")
    op.execute("DROP FUNCTION IF EXISTS public.prevent_hr_detected_differences_delete()")
    op.execute("DROP FUNCTION IF EXISTS public.prevent_hr_confirmed_changes_mutation()")

    op.execute("DROP TABLE IF EXISTS public.hr_reference_version_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.hr_monthly_reference_entries CASCADE")
    op.execute("DROP TABLE IF EXISTS public.hr_confirmed_changes CASCADE")
    op.execute("DROP TABLE IF EXISTS public.hr_detected_differences CASCADE")
    op.execute("DROP TABLE IF EXISTS public.hr_comparison_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS public.hr_monthly_references CASCADE")
    op.execute("DROP TABLE IF EXISTS public.hr_difference_origin_types CASCADE")
