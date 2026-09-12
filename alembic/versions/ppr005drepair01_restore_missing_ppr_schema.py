"""Repair a historically stamped-but-missing PPR schema prefix.

Some local databases were stamped at ``ppr005cread01`` after the PPR
revisions had been skipped outside Alembic.  A later normal upgrade then fails
at ``ppr005fevent01`` because its foreign keys refer to a table which the
stamped prefix says already exists.  This revision is deliberately placed
between 005C and 005F: healthy databases are a no-op, while the known all-or-
nothing missing prefix is restored before any dependent migration is run.

It never changes ``alembic_version`` itself and never deletes or recreates an
existing table.  A partial prefix is rejected rather than guessed at.
"""
from alembic import op


revision = "ppr005drepair01"
down_revision = "ppr005cread01"
branch_labels = None
depends_on = None


_PREFIX_TABLES = (
    "ppr_stage0_cohort_runs",
    "ppr_stage0_cohort_participants",
    "ppr_stage0_cohort_blockers",
    "ppr_stage1_general_runs",
    "ppr_stage1_general_participants",
    "ppr_stage_runs",
    "ppr_stage_run_participants",
    "ppr_migration_status_universes",
    "ppr_migration_status_universe_cohorts",
    "ppr_migration_section_status_projection",
)


def upgrade() -> None:
    # Do not turn a partially damaged schema into an unknown hybrid.  The
    # historical failure this repairs removed the complete PPR prefix.
    names = ",".join(repr(f"public.{name}") for name in _PREFIX_TABLES)
    op.execute(
        f"""
        DO $$ DECLARE present_count integer; BEGIN
          SELECT count(*) INTO present_count FROM unnest(ARRAY[{names}]::text[]) AS t(name)
          WHERE to_regclass(t.name) IS NOT NULL;
          IF present_count <> 0 AND present_count <> {len(_PREFIX_TABLES)} THEN
            RAISE EXCEPTION
              'Cannot repair ppr005drepair01: PPR prefix is partially present (% of {len(_PREFIX_TABLES)} tables)',
              present_count;
          END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.ppr_stage0_cohort_runs (
          stage0_cohort_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          run_kind TEXT NOT NULL CHECK (run_kind IN ('BASE','SUPPLEMENTAL')),
          supplemental_of_run_id BIGINT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
          source_batch_id BIGINT NOT NULL REFERENCES public.hr_import_batches(batch_id) ON DELETE RESTRICT,
          source_type TEXT NOT NULL CHECK (source_type = 'HR_CONTROL_LIST'),
          source_batch_status TEXT NOT NULL CHECK (source_batch_status IN ('APPLY_PENDING','APPLIED','PARTIALLY_APPLIED')),
          preview_fingerprint TEXT NOT NULL UNIQUE CHECK (length(preview_fingerprint)=64 AND preview_fingerprint ~ '^[0-9a-f]{64}$'),
          policy_version TEXT NOT NULL, source_snapshot JSONB NOT NULL,
          created_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
          frozen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT chk_ppr_s0_parent_kind CHECK ((run_kind='BASE' AND supplemental_of_run_id IS NULL) OR (run_kind='SUPPLEMENTAL' AND supplemental_of_run_id IS NOT NULL))
        );
        CREATE TABLE IF NOT EXISTS public.ppr_stage0_cohort_participants (
          stage0_participant_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          stage0_cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
          position INTEGER NOT NULL CHECK(position >= 1), employee_id BIGINT NOT NULL REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
          person_id BIGINT NOT NULL REFERENCES public.persons(person_id) ON DELETE RESTRICT,
          source_batch_id BIGINT NOT NULL REFERENCES public.hr_import_batches(batch_id) ON DELETE RESTRICT,
          source_row_id BIGINT NOT NULL REFERENCES public.hr_import_rows(row_id) ON DELETE RESTRICT,
          identity_provenance_record_id BIGINT NULL REFERENCES public.hr_import_normalized_records(normalized_record_id) ON DELETE RESTRICT,
          participant_snapshot_version INTEGER NOT NULL DEFAULT 1 CHECK(participant_snapshot_version=1),
          safe_fingerprint TEXT NOT NULL CHECK(length(safe_fingerprint)=64 AND safe_fingerprint ~ '^[0-9a-f]{64}$'),
          employee_state_version BIGINT NULL, person_state_version BIGINT NULL, ppr_lifecycle_version BIGINT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(stage0_cohort_run_id,position), UNIQUE(stage0_cohort_run_id,employee_id), UNIQUE(stage0_cohort_run_id,person_id)
        );
        CREATE TABLE IF NOT EXISTS public.ppr_stage0_cohort_blockers (
          stage0_blocker_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          stage0_cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
          employee_id BIGINT NULL REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
          person_id BIGINT NULL REFERENCES public.persons(person_id) ON DELETE RESTRICT,
          source_batch_id BIGINT NULL REFERENCES public.hr_import_batches(batch_id) ON DELETE RESTRICT,
          source_row_id BIGINT NULL REFERENCES public.hr_import_rows(row_id) ON DELETE RESTRICT,
          identity_provenance_record_id BIGINT NULL REFERENCES public.hr_import_normalized_records(normalized_record_id) ON DELETE RESTRICT,
          candidate_key TEXT NOT NULL CHECK(length(candidate_key)=64 AND candidate_key ~ '^[0-9a-f]{64}$'),
          category TEXT NOT NULL, reason_code TEXT NOT NULL, safe_detail TEXT NOT NULL,
          snapshot_version INTEGER NOT NULL DEFAULT 1 CHECK(snapshot_version=1),
          safe_fingerprint TEXT NOT NULL CHECK(length(safe_fingerprint)=64 AND safe_fingerprint ~ '^[0-9a-f]{64}$'),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(stage0_cohort_run_id,candidate_key,category,reason_code)
        );
        CREATE TABLE IF NOT EXISTS public.ppr_stage1_general_runs (
          stage1_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          stage0_cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
          status TEXT NOT NULL CHECK(status IN ('DRY_RUN_COMPLETED','APPROVED','RUNNING','PAUSED_ON_ERROR','COMPLETED_PENDING_REVIEW','ACCEPTED','CANCELLED')),
          preview_fingerprint TEXT NOT NULL UNIQUE CHECK(length(preview_fingerprint)=64 AND preview_fingerprint ~ '^[0-9a-f]{64}$'),
          policy_version TEXT NOT NULL, current_position INTEGER NOT NULL DEFAULT 1 CHECK(current_position>=1),
          created_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
          accepted_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(), accepted_at TIMESTAMPTZ NULL
        );
        CREATE TABLE IF NOT EXISTS public.ppr_stage1_general_participants (
          stage1_participant_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          stage1_run_id BIGINT NOT NULL REFERENCES public.ppr_stage1_general_runs(stage1_run_id) ON DELETE RESTRICT,
          position INTEGER NOT NULL CHECK(position>=1), employee_id BIGINT NOT NULL REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
          person_id BIGINT NOT NULL REFERENCES public.persons(person_id) ON DELETE RESTRICT,
          source_row_id BIGINT NOT NULL REFERENCES public.hr_import_rows(row_id) ON DELETE RESTRICT,
          participant_snapshot_version INTEGER NOT NULL DEFAULT 1 CHECK(participant_snapshot_version>=1),
          source_fingerprint TEXT NOT NULL CHECK(length(source_fingerprint)=64 AND source_fingerprint ~ '^[0-9a-f]{64}$'), person_updated_at TIMESTAMPTZ NULL,
          proposed_values JSONB NOT NULL, conflicts JSONB NOT NULL DEFAULT '[]'::jsonb,
          status TEXT NOT NULL CHECK(status IN ('PENDING','COMPLETED','ERROR','SKIPPED_BY_DECISION')),
          error_code TEXT NULL, error_detail TEXT NULL, completed_at TIMESTAMPTZ NULL,
          UNIQUE(stage1_run_id,position), UNIQUE(stage1_run_id,employee_id), UNIQUE(stage1_run_id,person_id)
        );
        CREATE TABLE IF NOT EXISTS public.ppr_stage_runs (
          stage_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          stage_code TEXT NOT NULL, stage0_cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
          status TEXT NOT NULL CHECK(status IN ('DRAFT','DRY_RUN_COMPLETED','APPROVED','RUNNING','PAUSED_ON_ERROR','COMPLETED_PENDING_REVIEW','ACCEPTED','CANCELLED')),
          preview_fingerprint TEXT NOT NULL CHECK(length(preview_fingerprint)=64 AND preview_fingerprint ~ '^[0-9a-f]{64}$'),
          policy_version TEXT NOT NULL, current_position INTEGER NOT NULL DEFAULT 0 CHECK(current_position>=0),
          safe_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(safe_snapshot)='object'),
          created_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
          approved_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
          accepted_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
          cancelled_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(), approved_at TIMESTAMPTZ NULL, accepted_at TIMESTAMPTZ NULL,
          paused_at TIMESTAMPTZ NULL, cancelled_at TIMESTAMPTZ NULL, paused_operation TEXT NULL,
          stopped_participant_id BIGINT NULL, last_error_code TEXT NULL, last_error_reference TEXT NULL, cancel_reason TEXT NULL,
          accepted_precondition_fingerprint TEXT NULL, acceptance_outcome JSONB NOT NULL DEFAULT '{}'::jsonb,
          CONSTRAINT uq_ppr_stage2_preview UNIQUE(stage_code,stage0_cohort_run_id,preview_fingerprint),
          CONSTRAINT chk_ppr_stage_runs_stage_policy CHECK ((stage_code='education' AND policy_version='EDU-KIND-ALLOWLIST-v1') OR (stage_code='training' AND policy_version='TRAINING-PROPOSAL-v1'))
        );
        CREATE TABLE IF NOT EXISTS public.ppr_stage_run_participants (
          stage_run_participant_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          stage_run_id BIGINT NOT NULL REFERENCES public.ppr_stage_runs(stage_run_id) ON DELETE RESTRICT,
          stage0_participant_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_participants(stage0_participant_id) ON DELETE RESTRICT,
          position INTEGER NOT NULL CHECK(position>=1), employee_id BIGINT NOT NULL REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
          person_id BIGINT NOT NULL REFERENCES public.persons(person_id) ON DELETE RESTRICT,
          participant_snapshot_version INTEGER NOT NULL DEFAULT 1 CHECK(participant_snapshot_version>=1),
          safe_fingerprint TEXT NOT NULL CHECK(length(safe_fingerprint)=64 AND safe_fingerprint ~ '^[0-9a-f]{64}$'),
          status TEXT NOT NULL CHECK(status IN ('PENDING','COMPLETED','ERROR','SKIPPED_BY_DECISION')),
          pmf_run_id BIGINT NULL UNIQUE REFERENCES public.personnel_migration_runs(run_id) ON DELETE RESTRICT,
          completed_at TIMESTAMPTZ NULL, error_code TEXT NULL, error_reference TEXT NULL, errored_at TIMESTAMPTZ NULL,
          skipped_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT, skipped_at TIMESTAMPTZ NULL, skip_reason TEXT NULL,
          CONSTRAINT uq_ppr_stage2_participant_position UNIQUE(stage_run_id,position),
          CONSTRAINT uq_ppr_stage2_participant_stage0 UNIQUE(stage_run_id,stage0_participant_id),
          CONSTRAINT uq_ppr_stage2_participant_employee UNIQUE(stage_run_id,employee_id)
        );
        ALTER TABLE public.ppr_stage_runs DROP CONSTRAINT IF EXISTS fk_ppr_stage2_stopped_participant;
        ALTER TABLE public.ppr_stage_runs ADD CONSTRAINT fk_ppr_stage2_stopped_participant FOREIGN KEY(stopped_participant_id) REFERENCES public.ppr_stage_run_participants(stage_run_participant_id) ON DELETE RESTRICT;
        CREATE TABLE IF NOT EXISTS public.ppr_migration_status_universes (
          universe_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          universe_key TEXT NOT NULL UNIQUE CHECK(length(universe_key)=64 AND universe_key ~ '^[0-9a-f]{64}$'),
          base_cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(), CHECK (base_cohort_run_id > 0)
        );
        CREATE TABLE IF NOT EXISTS public.ppr_migration_status_universe_cohorts (
          universe_id BIGINT NOT NULL REFERENCES public.ppr_migration_status_universes(universe_id) ON DELETE CASCADE,
          stage0_cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
          cohort_role TEXT NOT NULL CHECK(cohort_role IN ('BASE','SUPPLEMENTAL')),
          PRIMARY KEY(universe_id,stage0_cohort_run_id), UNIQUE(universe_id,cohort_role,stage0_cohort_run_id)
        );
        CREATE TABLE IF NOT EXISTS public.ppr_migration_section_status_projection (
          universe_id BIGINT NOT NULL REFERENCES public.ppr_migration_status_universes(universe_id) ON DELETE CASCADE,
          person_id BIGINT NOT NULL REFERENCES public.persons(person_id) ON DELETE RESTRICT,
          employee_context_id BIGINT NOT NULL REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
          org_unit_id BIGINT NULL REFERENCES public.org_units(unit_id) ON DELETE RESTRICT,
          section_code TEXT NOT NULL CHECK(section_code IN ('general','education','training')),
          status_code TEXT NOT NULL CHECK(status_code IN ('NOT_STARTED','PROCESSING','AUTO_READY','REVIEW_REQUIRED','CORRECTED_BY_HR','ACCEPTED','NO_SOURCE_DATA','NOT_APPLICABLE','BLOCKED','STALE','ERROR')),
          reason_code TEXT NOT NULL, source_cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
          source_row_id BIGINT NULL REFERENCES public.hr_import_rows(row_id) ON DELETE RESTRICT,
          stage_run_id BIGINT NULL REFERENCES public.ppr_stage_runs(stage_run_id) ON DELETE RESTRICT,
          stage1_run_id BIGINT NULL REFERENCES public.ppr_stage1_general_runs(stage1_run_id) ON DELETE RESTRICT,
          stage_participant_id BIGINT NULL REFERENCES public.ppr_stage_run_participants(stage_run_participant_id) ON DELETE RESTRICT,
          stage1_participant_id BIGINT NULL REFERENCES public.ppr_stage1_general_participants(stage1_participant_id) ON DELETE RESTRICT,
          pmf_run_id BIGINT NULL REFERENCES public.personnel_migration_runs(run_id) ON DELETE RESTRICT,
          evidence_kind TEXT NULL, policy_version TEXT NULL, parser_version TEXT NULL,
          source_fingerprint TEXT NOT NULL CHECK(length(source_fingerprint)=64), target_fingerprint TEXT NOT NULL CHECK(length(target_fingerprint)=64), binding_fingerprint TEXT NOT NULL CHECK(length(binding_fingerprint)=64),
          calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(), row_version BIGINT NOT NULL DEFAULT 1 CHECK(row_version >= 1),
          PRIMARY KEY(universe_id,person_id,section_code)
        );
        CREATE INDEX IF NOT EXISTS ix_ppr_s0_runs_batch_frozen ON public.ppr_stage0_cohort_runs(source_batch_id, frozen_at DESC);
        CREATE INDEX IF NOT EXISTS ix_ppr_s0_participants_employee ON public.ppr_stage0_cohort_participants(employee_id);
        CREATE INDEX IF NOT EXISTS ix_ppr_s0_participants_person ON public.ppr_stage0_cohort_participants(person_id);
        CREATE INDEX IF NOT EXISTS ix_ppr_migration_status_projection_scope ON public.ppr_migration_section_status_projection(universe_id,org_unit_id,person_id);
        CREATE INDEX IF NOT EXISTS ix_ppr_migration_status_projection_status ON public.ppr_migration_section_status_projection(universe_id,section_code,status_code);
        """
    )


def downgrade() -> None:
    # This is a repair boundary.  Existing or restored PPR data must never be
    # silently destroyed by a downgrade.
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM public.ppr_migration_status_universes)
             OR EXISTS (SELECT 1 FROM public.ppr_stage0_cohort_runs)
             OR EXISTS (SELECT 1 FROM public.ppr_stage1_general_runs)
             OR EXISTS (SELECT 1 FROM public.ppr_stage_runs) THEN
            RAISE EXCEPTION 'Cannot downgrade ppr005drepair01: restored PPR data exists';
          END IF;
        END $$;
        """
    )
