"""Preserve immutable evidence for safe personnel-order draft deletion.

Revision ID: pojson017
Revises: pojson016
"""
from alembic import op

revision = "pojson017"
down_revision = "pojson016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE public.personnel_order_draft_deletion_audit (
      audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      order_id BIGINT NOT NULL,
      order_snapshot JSONB NOT NULL,
      deleted_dependencies JSONB NOT NULL,
      actor_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
      reason_text TEXT NOT NULL,
      result_code TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_personnel_order_draft_deletion_audit_order_created
      ON public.personnel_order_draft_deletion_audit(order_id, created_at DESC);
    CREATE OR REPLACE FUNCTION public.guard_personnel_order_draft_deletion_audit() RETURNS trigger AS $$
    BEGIN RAISE EXCEPTION 'personnel_order_draft_deletion_audit is append-only'; END $$ LANGUAGE plpgsql;
    CREATE TRIGGER trg_guard_personnel_order_draft_deletion_audit
      BEFORE UPDATE OR DELETE ON public.personnel_order_draft_deletion_audit
      FOR EACH ROW EXECUTE FUNCTION public.guard_personnel_order_draft_deletion_audit();
    """)


def downgrade() -> None:
    op.execute("""
    DROP TRIGGER IF EXISTS trg_guard_personnel_order_draft_deletion_audit ON public.personnel_order_draft_deletion_audit;
    DROP FUNCTION IF EXISTS public.guard_personnel_order_draft_deletion_audit();
    DROP TABLE public.personnel_order_draft_deletion_audit;
    """)
