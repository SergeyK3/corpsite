"""Add an immutable audit sink for the narrow technical-order cleanup handler.

Revision ID: pojson015
Revises: pojson014
"""
from alembic import op

revision = "pojson015"
down_revision = "pojson014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No FK to personnel_orders: the row must survive the hard delete.
    op.execute("""
    CREATE TABLE public.technical_personnel_order_deletion_audit (
      audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      order_id BIGINT NOT NULL, order_snapshot JSONB NOT NULL,
      deleted_dependencies JSONB NOT NULL,
      actor_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
      reason_text TEXT NOT NULL, result_code TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now());
    CREATE INDEX ix_technical_order_cleanup_audit_order_created ON public.technical_personnel_order_deletion_audit(order_id, created_at DESC);
    CREATE OR REPLACE FUNCTION public.guard_technical_personnel_order_deletion_audit() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'technical_personnel_order_deletion_audit is append-only'; END $$ LANGUAGE plpgsql;
    CREATE TRIGGER trg_guard_technical_personnel_order_deletion_audit BEFORE UPDATE OR DELETE ON public.technical_personnel_order_deletion_audit FOR EACH ROW EXECUTE FUNCTION public.guard_technical_personnel_order_deletion_audit();
    CREATE TABLE public.technical_personnel_order_provenance_audit (
      audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      order_id BIGINT NOT NULL, previous_storage_json JSONB NOT NULL,
      confirmed_storage_json JSONB NOT NULL,
      actor_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
      reason_text TEXT NOT NULL, result_code TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now());
    CREATE OR REPLACE FUNCTION public.guard_technical_personnel_order_provenance_audit() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'technical_personnel_order_provenance_audit is append-only'; END $$ LANGUAGE plpgsql;
    CREATE TRIGGER trg_guard_technical_personnel_order_provenance_audit BEFORE UPDATE OR DELETE ON public.technical_personnel_order_provenance_audit FOR EACH ROW EXECUTE FUNCTION public.guard_technical_personnel_order_provenance_audit();
    INSERT INTO public.access_roles(code,name,description,access_level,level_rank,is_system) VALUES ('TECHNICAL_PERSONNEL_ORDER_CLEANUP','Technical personnel order cleanup','Preview and delete confirmed isolated technical personnel orders', 'ADMIN', 30, TRUE) ON CONFLICT (code) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_guard_technical_personnel_order_provenance_audit ON public.technical_personnel_order_provenance_audit")
    op.execute("DROP FUNCTION IF EXISTS public.guard_technical_personnel_order_provenance_audit()")
    op.execute("DROP TABLE public.technical_personnel_order_provenance_audit")
    op.execute("DROP TRIGGER IF EXISTS trg_guard_technical_personnel_order_deletion_audit ON public.technical_personnel_order_deletion_audit")
    op.execute("DROP FUNCTION IF EXISTS public.guard_technical_personnel_order_deletion_audit()")
    op.execute("DROP TABLE public.technical_personnel_order_deletion_audit")
    op.execute("DELETE FROM public.access_roles WHERE code='TECHNICAL_PERSONNEL_ORDER_CLEANUP'")
