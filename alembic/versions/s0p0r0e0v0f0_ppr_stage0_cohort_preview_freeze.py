"""Stage 0 PPR cohort PREVIEW/FREEZE persistence and RBAC."""
from alembic import op

revision = "s0p0r0e0v0f0"
down_revision = "m1n2o3p4q5r6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE public.ppr_stage0_cohort_runs (
      stage0_cohort_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      run_kind TEXT NOT NULL CHECK (run_kind IN ('BASE','SUPPLEMENTAL')),
      supplemental_of_run_id BIGINT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
      source_batch_id BIGINT NOT NULL REFERENCES public.hr_import_batches(batch_id) ON DELETE RESTRICT,
      source_type TEXT NOT NULL CHECK (source_type = 'HR_CONTROL_LIST'),
      source_batch_status TEXT NOT NULL CHECK (source_batch_status IN ('APPLY_PENDING','APPLIED','PARTIALLY_APPLIED')),
      preview_fingerprint TEXT NOT NULL UNIQUE CHECK (length(preview_fingerprint)=64 AND preview_fingerprint ~ '^[0-9a-f]{64}$'),
      policy_version TEXT NOT NULL,
      source_snapshot JSONB NOT NULL,
      created_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
      frozen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      CONSTRAINT chk_ppr_s0_parent_kind CHECK ((run_kind='BASE' AND supplemental_of_run_id IS NULL) OR (run_kind='SUPPLEMENTAL' AND supplemental_of_run_id IS NOT NULL))
    );
    CREATE INDEX ix_ppr_s0_runs_batch_frozen ON public.ppr_stage0_cohort_runs(source_batch_id, frozen_at DESC);
    CREATE INDEX ix_ppr_s0_runs_parent_frozen ON public.ppr_stage0_cohort_runs(supplemental_of_run_id, frozen_at DESC);
    CREATE TABLE public.ppr_stage0_cohort_participants (
      stage0_participant_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      stage0_cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
      position INTEGER NOT NULL CHECK(position >= 1),
      employee_id BIGINT NOT NULL REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
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
    CREATE INDEX ix_ppr_s0_participants_employee ON public.ppr_stage0_cohort_participants(employee_id);
    CREATE INDEX ix_ppr_s0_participants_person ON public.ppr_stage0_cohort_participants(person_id);
    CREATE TABLE public.ppr_stage0_cohort_blockers (
      stage0_blocker_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      stage0_cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
      employee_id BIGINT NULL REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
      person_id BIGINT NULL REFERENCES public.persons(person_id) ON DELETE RESTRICT,
      source_batch_id BIGINT NULL REFERENCES public.hr_import_batches(batch_id) ON DELETE RESTRICT,
      source_row_id BIGINT NULL REFERENCES public.hr_import_rows(row_id) ON DELETE RESTRICT,
      identity_provenance_record_id BIGINT NULL REFERENCES public.hr_import_normalized_records(normalized_record_id) ON DELETE RESTRICT,
      candidate_key TEXT NOT NULL CHECK(length(candidate_key)=64 AND candidate_key ~ '^[0-9a-f]{64}$'),
      category TEXT NOT NULL CHECK(category IN ('BLOCKED_NO_PERSON','BLOCKED_AMBIGUOUS_PERSON','BLOCKED_PERSON_MERGED_OR_DELETED','BLOCKED_SOURCE_MISSING','BLOCKED_SOURCE_AMBIGUOUS','BLOCKED_SOURCE_STATUS','BLOCKED_SOURCE_DELETION_OR_REBINDING','BLOCKED_MATERIALIZATION_PATH')),
      reason_code TEXT NOT NULL, safe_detail TEXT NOT NULL,
      snapshot_version INTEGER NOT NULL DEFAULT 1 CHECK(snapshot_version=1),
      safe_fingerprint TEXT NOT NULL CHECK(length(safe_fingerprint)=64 AND safe_fingerprint ~ '^[0-9a-f]{64}$'),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE(stage0_cohort_run_id,candidate_key,category,reason_code)
    );
    CREATE INDEX ix_ppr_s0_blockers_run_category ON public.ppr_stage0_cohort_blockers(stage0_cohort_run_id,category);
    DO $$ DECLARE role_id BIGINT; grantor BIGINT; permission_id BIGINT; BEGIN
      SELECT r.role_id INTO role_id FROM public.roles r WHERE r.code='HR_HEAD';
      IF role_id IS NULL THEN RAISE EXCEPTION 'Stage 0 requires HR_HEAD role'; END IF;
      SELECT user_id INTO grantor FROM public.users WHERE is_active=true ORDER BY user_id LIMIT 1;
      IF grantor IS NULL THEN RAISE EXCEPTION 'Stage 0 requires active grantor user'; END IF;
      INSERT INTO public.access_roles(code,name,description,access_level,level_rank,is_system)
      VALUES('PPR_STAGE0_COHORT_MANAGE','PPR Stage 0 cohort management','Preview and freeze PPR migration cohorts','MANAGER',20,true)
      ON CONFLICT(code) DO NOTHING;
      SELECT access_role_id INTO permission_id FROM public.access_roles WHERE code='PPR_STAGE0_COHORT_MANAGE';
      INSERT INTO public.access_grants(access_role_id,target_type,target_id,granted_by_user_id,reason)
      SELECT permission_id,'ROLE',role_id,grantor,'PPR Stage 0 cohort management for HR_HEAD'
      WHERE NOT EXISTS (SELECT 1 FROM public.access_grants WHERE access_role_id=permission_id AND target_type='ROLE' AND target_id=role_id);
    END $$;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM public.access_grants USING public.access_roles WHERE access_grants.access_role_id=access_roles.access_role_id AND access_roles.code='PPR_STAGE0_COHORT_MANAGE'")
    op.execute("DELETE FROM public.access_roles WHERE code='PPR_STAGE0_COHORT_MANAGE'")
    op.execute("DROP TABLE public.ppr_stage0_cohort_blockers")
    op.execute("DROP TABLE public.ppr_stage0_cohort_participants")
    op.execute("DROP TABLE public.ppr_stage0_cohort_runs")
