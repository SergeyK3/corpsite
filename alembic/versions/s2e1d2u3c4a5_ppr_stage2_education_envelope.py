"""Stage 2 education thin envelope over PMF drafts."""
from alembic import op

revision = "s2e1d2u3c4a5"
down_revision = "s1g0e1n2r3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE public.ppr_stage_runs (
      stage_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      stage_code TEXT NOT NULL CHECK(stage_code='education'),
      stage0_cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
      status TEXT NOT NULL CHECK(status IN ('DRAFT','DRY_RUN_COMPLETED','APPROVED','RUNNING','PAUSED_ON_ERROR','COMPLETED_PENDING_REVIEW','ACCEPTED','CANCELLED')),
      preview_fingerprint TEXT NOT NULL CHECK(length(preview_fingerprint)=64 AND preview_fingerprint ~ '^[0-9a-f]{64}$'),
      policy_version TEXT NOT NULL CHECK(policy_version='EDU-KIND-ALLOWLIST-v1'),
      current_position INTEGER NOT NULL DEFAULT 0 CHECK(current_position>=0),
      safe_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(safe_snapshot)='object'),
      created_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
      approved_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
      accepted_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
      cancelled_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      approved_at TIMESTAMPTZ NULL, accepted_at TIMESTAMPTZ NULL,
      paused_at TIMESTAMPTZ NULL, cancelled_at TIMESTAMPTZ NULL,
      paused_operation TEXT NULL CHECK(paused_operation IN ('PARTICIPANT_EXECUTION','ACCEPTANCE')),
      stopped_participant_id BIGINT NULL,
      last_error_code TEXT NULL, last_error_reference TEXT NULL,
      cancel_reason TEXT NULL,
      accepted_precondition_fingerprint TEXT NULL CHECK(accepted_precondition_fingerprint IS NULL OR (length(accepted_precondition_fingerprint)=64 AND accepted_precondition_fingerprint ~ '^[0-9a-f]{64}$')),
      acceptance_outcome JSONB NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(acceptance_outcome)='object'),
      CONSTRAINT uq_ppr_stage2_preview UNIQUE(stage_code,stage0_cohort_run_id,preview_fingerprint),
      CONSTRAINT chk_ppr_stage2_approval CHECK(
        (status IN ('DRAFT','DRY_RUN_COMPLETED') AND approved_by_user_id IS NULL AND approved_at IS NULL)
        OR (status IN ('APPROVED','RUNNING','PAUSED_ON_ERROR','COMPLETED_PENDING_REVIEW','ACCEPTED') AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL)
        OR (status='CANCELLED' AND ((approved_by_user_id IS NULL AND approved_at IS NULL) OR (approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL)))
      ),
      CONSTRAINT chk_ppr_stage2_acceptance CHECK(
        (status='ACCEPTED' AND accepted_by_user_id IS NOT NULL AND accepted_at IS NOT NULL AND accepted_precondition_fingerprint IS NOT NULL AND acceptance_outcome <> '{}'::jsonb)
        OR (status<>'ACCEPTED' AND accepted_by_user_id IS NULL AND accepted_at IS NULL AND accepted_precondition_fingerprint IS NULL AND acceptance_outcome='{}'::jsonb)
      ),
      CONSTRAINT chk_ppr_stage2_cancel CHECK(
        (status='CANCELLED' AND cancelled_by_user_id IS NOT NULL AND cancelled_at IS NOT NULL AND btrim(cancel_reason) <> '')
        OR (status<>'CANCELLED' AND cancelled_by_user_id IS NULL AND cancelled_at IS NULL AND cancel_reason IS NULL)
      ),
      CONSTRAINT chk_ppr_stage2_pause CHECK(
        (status='PAUSED_ON_ERROR' AND paused_at IS NOT NULL AND paused_operation IS NOT NULL AND btrim(last_error_code)<>'' AND btrim(last_error_reference)<>'')
        OR (status<>'PAUSED_ON_ERROR' AND paused_at IS NULL AND paused_operation IS NULL AND stopped_participant_id IS NULL AND last_error_code IS NULL AND last_error_reference IS NULL)
      )
    );
    CREATE TABLE public.ppr_stage_run_participants (
      stage_run_participant_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      stage_run_id BIGINT NOT NULL REFERENCES public.ppr_stage_runs(stage_run_id) ON DELETE RESTRICT,
      stage0_participant_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_participants(stage0_participant_id) ON DELETE RESTRICT,
      position INTEGER NOT NULL CHECK(position>=1),
      employee_id BIGINT NOT NULL REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
      person_id BIGINT NOT NULL REFERENCES public.persons(person_id) ON DELETE RESTRICT,
      participant_snapshot_version INTEGER NOT NULL DEFAULT 1 CHECK(participant_snapshot_version>=1),
      safe_fingerprint TEXT NOT NULL CHECK(length(safe_fingerprint)=64 AND safe_fingerprint ~ '^[0-9a-f]{64}$'),
      status TEXT NOT NULL CHECK(status IN ('PENDING','COMPLETED','ERROR','SKIPPED_BY_DECISION')),
      pmf_run_id BIGINT NULL UNIQUE REFERENCES public.personnel_migration_runs(run_id) ON DELETE RESTRICT,
      completed_at TIMESTAMPTZ NULL,
      error_code TEXT NULL, error_reference TEXT NULL, errored_at TIMESTAMPTZ NULL,
      skipped_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
      skipped_at TIMESTAMPTZ NULL, skip_reason TEXT NULL,
      CONSTRAINT uq_ppr_stage2_participant_position UNIQUE(stage_run_id,position),
      CONSTRAINT uq_ppr_stage2_participant_stage0 UNIQUE(stage_run_id,stage0_participant_id),
      CONSTRAINT uq_ppr_stage2_participant_employee UNIQUE(stage_run_id,employee_id),
      CONSTRAINT chk_ppr_stage2_participant_complete CHECK((status='COMPLETED' AND completed_at IS NOT NULL) OR (status<>'COMPLETED' AND completed_at IS NULL)),
      CONSTRAINT chk_ppr_stage2_participant_error CHECK((status='ERROR' AND error_code IS NOT NULL AND error_reference IS NOT NULL AND errored_at IS NOT NULL) OR (status<>'ERROR' AND error_code IS NULL AND error_reference IS NULL AND errored_at IS NULL)),
      CONSTRAINT chk_ppr_stage2_participant_skip CHECK((status='SKIPPED_BY_DECISION' AND skipped_by_user_id IS NOT NULL AND skipped_at IS NOT NULL AND btrim(skip_reason)<>'') OR (status<>'SKIPPED_BY_DECISION' AND skipped_by_user_id IS NULL AND skipped_at IS NULL AND skip_reason IS NULL))
    );
    ALTER TABLE public.ppr_stage_runs ADD CONSTRAINT fk_ppr_stage2_stopped_participant FOREIGN KEY(stopped_participant_id) REFERENCES public.ppr_stage_run_participants(stage_run_participant_id) ON DELETE RESTRICT;
    ALTER TABLE public.ppr_stage_runs ADD CONSTRAINT chk_ppr_stage2_pause_target CHECK((status<>'PAUSED_ON_ERROR') OR (paused_operation='PARTICIPANT_EXECUTION' AND stopped_participant_id IS NOT NULL) OR (paused_operation='ACCEPTANCE' AND stopped_participant_id IS NULL));
    CREATE INDEX ix_ppr_stage2_runs_cohort_created ON public.ppr_stage_runs(stage0_cohort_run_id,stage_code,created_at DESC);
    CREATE INDEX ix_ppr_stage2_runs_status_created ON public.ppr_stage_runs(status,created_at DESC);
    CREATE INDEX ix_ppr_stage2_runs_stopped ON public.ppr_stage_runs(stopped_participant_id);
    CREATE INDEX ix_ppr_stage2_participants_run_status_position ON public.ppr_stage_run_participants(stage_run_id,status,position);
    CREATE INDEX ix_ppr_stage2_participants_run_position ON public.ppr_stage_run_participants(stage_run_id,position);
    CREATE INDEX ix_ppr_stage2_participants_employee ON public.ppr_stage_run_participants(employee_id);
    CREATE INDEX ix_ppr_stage2_participants_person ON public.ppr_stage_run_participants(person_id);
    CREATE INDEX ix_ppr_stage2_participants_stage0 ON public.ppr_stage_run_participants(stage0_participant_id);
    CREATE UNIQUE INDEX uq_pmf_stage2_run_key ON public.personnel_migration_runs ((metadata #>> '{stage2,deterministic_run_key}')) WHERE metadata ? 'stage2';
    CREATE UNIQUE INDEX uq_pmf_stage2_item_key ON public.personnel_migration_items(run_id,source_record_id) WHERE source_kind='stage2_control_list_fragment';
    DO $$ DECLARE rid BIGINT; grantor BIGINT; pid BIGINT; BEGIN
      SELECT role_id INTO rid FROM public.roles WHERE code='HR_HEAD';
      SELECT user_id INTO grantor FROM public.users WHERE is_active=true ORDER BY user_id LIMIT 1;
      IF rid IS NULL OR grantor IS NULL THEN RAISE EXCEPTION 'Stage 2 requires HR_HEAD and active grantor'; END IF;
      INSERT INTO public.access_roles(code,name,description,access_level,level_rank,is_system)
      VALUES('PPR_STAGE2_EDUCATION_MANAGE','PPR Stage 2 education','Manage Stage 2 education drafts','MANAGER',20,true)
      ON CONFLICT(code) DO NOTHING;
      SELECT access_role_id INTO pid FROM public.access_roles WHERE code='PPR_STAGE2_EDUCATION_MANAGE';
      INSERT INTO public.access_grants(access_role_id,target_type,target_id,granted_by_user_id,reason)
      SELECT pid,'ROLE',rid,grantor,'PPR Stage 2 education for HR_HEAD'
      WHERE NOT EXISTS(SELECT 1 FROM public.access_grants WHERE access_role_id=pid AND target_type='ROLE' AND target_id=rid);
    END $$;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.uq_pmf_stage2_item_key")
    op.execute("DROP INDEX IF EXISTS public.uq_pmf_stage2_run_key")
    op.execute("DELETE FROM public.access_grants USING public.access_roles WHERE access_grants.access_role_id=access_roles.access_role_id AND access_roles.code='PPR_STAGE2_EDUCATION_MANAGE'")
    op.execute("DELETE FROM public.access_roles WHERE code='PPR_STAGE2_EDUCATION_MANAGE'")
    op.execute("ALTER TABLE public.ppr_stage_runs DROP CONSTRAINT IF EXISTS fk_ppr_stage2_stopped_participant")
    op.execute("DROP TABLE IF EXISTS public.ppr_stage_run_participants")
    op.execute("DROP TABLE IF EXISTS public.ppr_stage_runs")
