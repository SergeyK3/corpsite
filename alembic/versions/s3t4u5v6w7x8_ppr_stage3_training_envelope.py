"""Stage 3 training extension of the shared PPR stage envelope."""
from alembic import op

revision = "ppr3training001"
down_revision = "s2e2f3g4h5i6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE public.ppr_stage_runs DROP CONSTRAINT IF EXISTS ppr_stage_runs_stage_code_check;
    ALTER TABLE public.ppr_stage_runs DROP CONSTRAINT IF EXISTS ppr_stage_runs_policy_version_check;
    ALTER TABLE public.ppr_stage_runs
      ADD CONSTRAINT chk_ppr_stage_runs_stage_policy CHECK (
        (stage_code='education' AND policy_version='EDU-KIND-ALLOWLIST-v1')
        OR (stage_code='training' AND policy_version='TRAINING-PROPOSAL-v1')
      );
    CREATE UNIQUE INDEX IF NOT EXISTS uq_pmf_stage3_training_run_key
      ON public.personnel_migration_runs ((metadata #>> '{stage3,deterministic_run_key}'))
      WHERE metadata ? 'stage3';
    CREATE UNIQUE INDEX IF NOT EXISTS uq_pmf_stage3_training_item_key
      ON public.personnel_migration_items(run_id, source_record_id)
      WHERE source_kind='stage3_training_proposal';
    DO $$ DECLARE rid BIGINT; grantor BIGINT; pid BIGINT; BEGIN
      SELECT role_id INTO rid FROM public.roles WHERE code='HR_HEAD';
      SELECT user_id INTO grantor FROM public.users WHERE is_active=true ORDER BY user_id LIMIT 1;
      IF rid IS NULL OR grantor IS NULL THEN RAISE EXCEPTION 'Stage 3 requires HR_HEAD and active grantor'; END IF;
      INSERT INTO public.access_roles(code,name,description,access_level,level_rank,is_system)
      VALUES('PPR_STAGE3_TRAINING_MANAGE','PPR Stage 3 training','Manage Stage 3 training drafts','MANAGER',20,true)
      ON CONFLICT(code) DO NOTHING;
      INSERT INTO public.access_roles(code,name,description,access_level,level_rank,is_system)
      VALUES('VIEW_TRAINING_CERTIFICATE_DETAILS','View training certificate details','View restricted training certificate numbers','MANAGER',20,true)
      ON CONFLICT(code) DO NOTHING;
      SELECT access_role_id INTO pid FROM public.access_roles WHERE code='PPR_STAGE3_TRAINING_MANAGE';
      INSERT INTO public.access_grants(access_role_id,target_type,target_id,granted_by_user_id,reason)
      SELECT pid,'ROLE',rid,grantor,'PPR Stage 3 training for HR_HEAD'
      WHERE NOT EXISTS(SELECT 1 FROM public.access_grants WHERE access_role_id=pid AND target_type='ROLE' AND target_id=rid);
      SELECT access_role_id INTO pid FROM public.access_roles WHERE code='VIEW_TRAINING_CERTIFICATE_DETAILS';
      INSERT INTO public.access_grants(access_role_id,target_type,target_id,granted_by_user_id,reason)
      SELECT pid,'ROLE',rid,grantor,'Restricted training certificate details for HR_HEAD'
      WHERE NOT EXISTS(SELECT 1 FROM public.access_grants WHERE access_role_id=pid AND target_type='ROLE' AND target_id=rid);
    END $$;
    """)


def downgrade() -> None:
    op.execute("""
    DROP INDEX IF EXISTS public.uq_pmf_stage3_training_item_key;
    DROP INDEX IF EXISTS public.uq_pmf_stage3_training_run_key;
    DELETE FROM public.access_grants USING public.access_roles WHERE access_grants.access_role_id=access_roles.access_role_id AND access_roles.code IN ('PPR_STAGE3_TRAINING_MANAGE','VIEW_TRAINING_CERTIFICATE_DETAILS');
    DELETE FROM public.access_roles WHERE code IN ('PPR_STAGE3_TRAINING_MANAGE','VIEW_TRAINING_CERTIFICATE_DETAILS');
    ALTER TABLE public.ppr_stage_runs DROP CONSTRAINT IF EXISTS chk_ppr_stage_runs_stage_policy;
    ALTER TABLE public.ppr_stage_runs ADD CONSTRAINT ppr_stage_runs_stage_code_check CHECK(stage_code='education');
    ALTER TABLE public.ppr_stage_runs ADD CONSTRAINT ppr_stage_runs_policy_version_check CHECK(policy_version='EDU-KIND-ALLOWLIST-v1');
    """)
