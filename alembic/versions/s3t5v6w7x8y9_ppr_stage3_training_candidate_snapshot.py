"""Require an immutable structured TrainingCandidate snapshot for Stage 3."""
from alembic import op


revision = "ppr3trainingsnap01"
down_revision = "ppr3training001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # safe_snapshot is the shared envelope's existing JSONB snapshot field.  A
    # NOT VALID CHECK preserves pre-existing data but is enforced for all new
    # training runs; education retains its established empty-object contract.
    op.execute("""
    ALTER TABLE public.ppr_stage_runs
      ADD CONSTRAINT chk_ppr_stage3_training_candidate_snapshot
      CHECK (
        stage_code <> 'training'
        OR (
          safe_snapshot ? 'training_candidates'
          AND safe_snapshot ? 'policy_version'
          AND safe_snapshot ? 'parser_version'
          AND jsonb_typeof(safe_snapshot->'training_candidates') = 'object'
        )
      ) NOT VALID;
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE public.ppr_stage_runs
      DROP CONSTRAINT IF EXISTS chk_ppr_stage3_training_candidate_snapshot;
    """)
