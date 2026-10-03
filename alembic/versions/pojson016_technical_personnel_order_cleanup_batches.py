"""Add immutable batch audit correlation for technical-order cleanup.

Revision ID: pojson016
Revises: pojson015
"""
from alembic import op

revision = "pojson016"
down_revision = "pojson015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE public.technical_personnel_order_deletion_audit
      ADD COLUMN batch_id UUID NULL;
    CREATE INDEX ix_technical_order_cleanup_audit_batch
      ON public.technical_personnel_order_deletion_audit(batch_id, created_at DESC);
    CREATE UNIQUE INDEX uq_technical_order_cleanup_audit_batch_order
      ON public.technical_personnel_order_deletion_audit(batch_id, order_id)
      WHERE batch_id IS NOT NULL;

    CREATE TABLE public.technical_personnel_order_cleanup_batch_audit (
      batch_id UUID PRIMARY KEY,
      order_ids JSONB NOT NULL,
      planned_deletions JSONB NOT NULL,
      actor_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
      reason_text TEXT NOT NULL,
      result_code TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    ALTER TABLE public.technical_personnel_order_deletion_audit
      ADD CONSTRAINT fk_technical_order_cleanup_audit_batch
      FOREIGN KEY (batch_id)
      REFERENCES public.technical_personnel_order_cleanup_batch_audit(batch_id)
      ON DELETE RESTRICT;
    CREATE OR REPLACE FUNCTION public.guard_technical_personnel_order_cleanup_batch_audit() RETURNS trigger AS $$
    BEGIN RAISE EXCEPTION 'technical_personnel_order_cleanup_batch_audit is append-only'; END $$ LANGUAGE plpgsql;
    CREATE TRIGGER trg_guard_technical_personnel_order_cleanup_batch_audit
      BEFORE UPDATE OR DELETE ON public.technical_personnel_order_cleanup_batch_audit
      FOR EACH ROW EXECUTE FUNCTION public.guard_technical_personnel_order_cleanup_batch_audit();
    """)


def downgrade() -> None:
    op.execute("""
    DROP TRIGGER IF EXISTS trg_guard_technical_personnel_order_cleanup_batch_audit ON public.technical_personnel_order_cleanup_batch_audit;
    DROP FUNCTION IF EXISTS public.guard_technical_personnel_order_cleanup_batch_audit();
    ALTER TABLE public.technical_personnel_order_deletion_audit DROP CONSTRAINT IF EXISTS fk_technical_order_cleanup_audit_batch;
    DROP TABLE public.technical_personnel_order_cleanup_batch_audit;
    DROP INDEX IF EXISTS public.uq_technical_order_cleanup_audit_batch_order;
    DROP INDEX IF EXISTS public.ix_technical_order_cleanup_audit_batch;
    ALTER TABLE public.technical_personnel_order_deletion_audit DROP COLUMN batch_id;
    """)
