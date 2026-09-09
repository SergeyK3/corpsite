"""Stage 1 general-information draft run persistence."""
from alembic import op

revision = "s1g0e1n2r3a4"
down_revision = "s0p0r0e0v0f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    INSERT INTO public.personnel_migration_domains(domain_code,display_name,description,is_enabled,target_table_names,control_list_columns)
    VALUES('general_information','PPR Stage 1 general information','Accepted general-information values from control list',true,'["persons","personnel_record_metadata"]'::jsonb,'["full_name","iin","birth_date"]'::jsonb)
    ON CONFLICT(domain_code) DO NOTHING;
    CREATE TABLE public.ppr_stage1_general_runs (
      stage1_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      stage0_cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
      status TEXT NOT NULL CHECK(status IN ('DRY_RUN_COMPLETED','APPROVED','RUNNING','PAUSED_ON_ERROR','COMPLETED_PENDING_REVIEW','ACCEPTED','CANCELLED')),
      preview_fingerprint TEXT NOT NULL UNIQUE CHECK(length(preview_fingerprint)=64 AND preview_fingerprint ~ '^[0-9a-f]{64}$'),
      policy_version TEXT NOT NULL, current_position INTEGER NOT NULL DEFAULT 1 CHECK(current_position>=1),
      created_by_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
      accepted_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(), accepted_at TIMESTAMPTZ NULL
    );
    CREATE TABLE public.ppr_stage1_general_participants (
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
    CREATE INDEX ix_ppr_s1_runs_cohort_created ON public.ppr_stage1_general_runs(stage0_cohort_run_id,created_at DESC);
    CREATE INDEX ix_ppr_s1_participants_run_status ON public.ppr_stage1_general_participants(stage1_run_id,status,position);
    DO $$ DECLARE rid BIGINT; grantor BIGINT; pid BIGINT; BEGIN
      SELECT role_id INTO rid FROM public.roles WHERE code='HR_HEAD'; SELECT user_id INTO grantor FROM public.users WHERE is_active=true ORDER BY user_id LIMIT 1;
      IF rid IS NULL OR grantor IS NULL THEN RAISE EXCEPTION 'Stage 1 requires HR_HEAD and active grantor'; END IF;
      INSERT INTO public.access_roles(code,name,description,access_level,level_rank,is_system) VALUES('PPR_STAGE1_GENERAL_MANAGE','PPR Stage 1 general information','Manage Stage 1 drafts','MANAGER',20,true) ON CONFLICT(code) DO NOTHING;
      SELECT access_role_id INTO pid FROM public.access_roles WHERE code='PPR_STAGE1_GENERAL_MANAGE';
      INSERT INTO public.access_grants(access_role_id,target_type,target_id,granted_by_user_id,reason) SELECT pid,'ROLE',rid,grantor,'Stage 1 general information for HR_HEAD' WHERE NOT EXISTS(SELECT 1 FROM public.access_grants WHERE access_role_id=pid AND target_type='ROLE' AND target_id=rid);
    END $$;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM public.access_grants USING public.access_roles WHERE access_grants.access_role_id=access_roles.access_role_id AND access_roles.code='PPR_STAGE1_GENERAL_MANAGE'")
    op.execute("DELETE FROM public.access_roles WHERE code='PPR_STAGE1_GENERAL_MANAGE'")
    op.execute("DROP TABLE public.ppr_stage1_general_participants")
    op.execute("DROP TABLE public.ppr_stage1_general_runs")
    op.execute("DELETE FROM public.personnel_migration_domains WHERE domain_code='general_information'")
