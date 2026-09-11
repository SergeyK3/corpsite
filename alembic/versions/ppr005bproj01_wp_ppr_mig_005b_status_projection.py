"""WP-PPR-MIG-005B safe persisted migration-status read model.

No backfill is performed here: a caller must explicitly create/rebuild a universe.
"""
from alembic import op

revision = "ppr005bproj01"
down_revision = "ppr3trainingsnap01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE public.ppr_migration_status_universes (
      universe_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      universe_key TEXT NOT NULL UNIQUE CHECK(length(universe_key)=64 AND universe_key ~ '^[0-9a-f]{64}$'),
      base_cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      CHECK (base_cohort_run_id > 0)
    );
    CREATE TABLE public.ppr_migration_status_universe_cohorts (
      universe_id BIGINT NOT NULL REFERENCES public.ppr_migration_status_universes(universe_id) ON DELETE CASCADE,
      stage0_cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
      cohort_role TEXT NOT NULL CHECK(cohort_role IN ('BASE','SUPPLEMENTAL')),
      PRIMARY KEY(universe_id,stage0_cohort_run_id),
      UNIQUE(universe_id,cohort_role,stage0_cohort_run_id)
    );
    CREATE TABLE public.ppr_migration_section_status_projection (
      universe_id BIGINT NOT NULL REFERENCES public.ppr_migration_status_universes(universe_id) ON DELETE CASCADE,
      person_id BIGINT NOT NULL REFERENCES public.persons(person_id) ON DELETE RESTRICT,
      employee_context_id BIGINT NOT NULL REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
      org_unit_id BIGINT NULL REFERENCES public.org_units(unit_id) ON DELETE RESTRICT,
      section_code TEXT NOT NULL CHECK(section_code IN ('general','education','training')),
      status_code TEXT NOT NULL CHECK(status_code IN ('NOT_STARTED','PROCESSING','AUTO_READY','REVIEW_REQUIRED','CORRECTED_BY_HR','ACCEPTED','NO_SOURCE_DATA','NOT_APPLICABLE','BLOCKED','STALE','ERROR')),
      reason_code TEXT NOT NULL,
      source_cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
      source_row_id BIGINT NULL REFERENCES public.hr_import_rows(row_id) ON DELETE RESTRICT,
      stage_run_id BIGINT NULL REFERENCES public.ppr_stage_runs(stage_run_id) ON DELETE RESTRICT,
      stage1_run_id BIGINT NULL REFERENCES public.ppr_stage1_general_runs(stage1_run_id) ON DELETE RESTRICT,
      stage_participant_id BIGINT NULL REFERENCES public.ppr_stage_run_participants(stage_run_participant_id) ON DELETE RESTRICT,
      stage1_participant_id BIGINT NULL REFERENCES public.ppr_stage1_general_participants(stage1_participant_id) ON DELETE RESTRICT,
      pmf_run_id BIGINT NULL REFERENCES public.personnel_migration_runs(run_id) ON DELETE RESTRICT,
      evidence_kind TEXT NULL,
      policy_version TEXT NULL,
      parser_version TEXT NULL,
      source_fingerprint TEXT NOT NULL CHECK(length(source_fingerprint)=64),
      target_fingerprint TEXT NOT NULL CHECK(length(target_fingerprint)=64),
      binding_fingerprint TEXT NOT NULL CHECK(length(binding_fingerprint)=64),
      calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      row_version BIGINT NOT NULL DEFAULT 1 CHECK(row_version >= 1),
      PRIMARY KEY(universe_id,person_id,section_code)
    );
    CREATE INDEX ix_ppr_migration_status_projection_scope ON public.ppr_migration_section_status_projection(universe_id,org_unit_id,person_id);
    CREATE INDEX ix_ppr_migration_status_projection_status ON public.ppr_migration_section_status_projection(universe_id,section_code,status_code);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.ppr_migration_section_status_projection")
    op.execute("DROP TABLE IF EXISTS public.ppr_migration_status_universe_cohorts")
    op.execute("DROP TABLE IF EXISTS public.ppr_migration_status_universes")
