"""Idempotent attempt creation.

Revision ID: trn003
Revises: trn002
"""
from alembic import op

revision = "trn003"
down_revision = "trn002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE public.training_attempts ADD COLUMN idempotency_key TEXT;
        CREATE UNIQUE INDEX uq_training_attempt_start_key
          ON public.training_attempts(assignment_id, idempotency_key)
          WHERE idempotency_key IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX public.uq_training_attempt_start_key")
    op.execute("ALTER TABLE public.training_attempts DROP COLUMN idempotency_key")
