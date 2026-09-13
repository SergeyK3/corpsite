"""Allow Stage 0 cohorts sourced directly from canonical HR relations.

Import cohorts retain their mandatory import-batch/row provenance.  Canonical
cohorts use the explicit CANONICAL_HR source and therefore have no invented
import batch or row.
"""
from alembic import op

revision = "ppr005jcanon01"
down_revision = "ppr005iadd01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      ALTER TABLE public.ppr_stage0_cohort_runs
        DROP CONSTRAINT IF EXISTS chk_ppr_s0_source_type,
        DROP CONSTRAINT IF EXISTS chk_ppr_s0_batch_status,
        DROP CONSTRAINT IF EXISTS ppr_stage0_cohort_runs_source_type_check,
        DROP CONSTRAINT IF EXISTS ppr_stage0_cohort_runs_source_batch_status_check;
      ALTER TABLE public.ppr_stage0_cohort_runs
        ALTER COLUMN source_batch_id DROP NOT NULL;
      ALTER TABLE public.ppr_stage0_cohort_participants
        ALTER COLUMN source_batch_id DROP NOT NULL,
        ALTER COLUMN source_row_id DROP NOT NULL;
      ALTER TABLE public.ppr_stage0_cohort_runs
        ADD CONSTRAINT chk_ppr_s0_source_type
          CHECK (source_type IN ('HR_CONTROL_LIST','CANONICAL_HR')),
        ADD CONSTRAINT chk_ppr_s0_source_binding CHECK (
          (source_type='HR_CONTROL_LIST'
             AND source_batch_status IN ('APPLY_PENDING','APPLIED','PARTIALLY_APPLIED')
             AND source_batch_id IS NOT NULL)
          OR
          (source_type='CANONICAL_HR'
             AND source_batch_status='CANONICAL'
             AND source_batch_id IS NULL)
        );
    """)


def downgrade() -> None:
    op.execute("""
      DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM public.ppr_stage0_cohort_runs WHERE source_type='CANONICAL_HR') THEN
          RAISE EXCEPTION 'Cannot downgrade ppr005jcanon01: canonical Stage 0 cohorts exist';
        END IF;
      END $$;
      ALTER TABLE public.ppr_stage0_cohort_runs
        DROP CONSTRAINT chk_ppr_s0_source_binding,
        DROP CONSTRAINT chk_ppr_s0_source_type;
      ALTER TABLE public.ppr_stage0_cohort_runs
        ALTER COLUMN source_batch_id SET NOT NULL;
      ALTER TABLE public.ppr_stage0_cohort_participants
        ALTER COLUMN source_batch_id SET NOT NULL,
        ALTER COLUMN source_row_id SET NOT NULL;
      ALTER TABLE public.ppr_stage0_cohort_runs
        ADD CONSTRAINT chk_ppr_s0_source_type CHECK (source_type = 'HR_CONTROL_LIST'),
        ADD CONSTRAINT chk_ppr_s0_batch_status CHECK (source_batch_status IN ('APPLY_PENDING','APPLIED','PARTIALLY_APPLIED'));
    """)
