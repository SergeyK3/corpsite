"""Keep deleted DRAFT personnel orders as immutable audit evidence.

Revision ID: pojson018
Revises: pojson017
"""
from alembic import op

revision = "pojson018"
down_revision = "pojson017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE public.personnel_orders
      ADD COLUMN deleted_at TIMESTAMPTZ NULL,
      ADD COLUMN deleted_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
      ADD COLUMN deletion_reason TEXT NULL;
    CREATE INDEX ix_personnel_orders_active ON public.personnel_orders(order_id) WHERE deleted_at IS NULL;
    ALTER TABLE public.personnel_order_draft_deletion_audit
      ADD COLUMN deletion_mode TEXT NOT NULL DEFAULT 'HARD_DELETE';
    ALTER TABLE public.personnel_order_draft_deletion_audit
      ADD CONSTRAINT ck_personnel_order_draft_deletion_audit_mode
      CHECK (deletion_mode IN ('HARD_DELETE', 'SOFT_DELETE'));
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE public.personnel_order_draft_deletion_audit
      DROP CONSTRAINT IF EXISTS ck_personnel_order_draft_deletion_audit_mode;
    ALTER TABLE public.personnel_order_draft_deletion_audit DROP COLUMN IF EXISTS deletion_mode;
    DROP INDEX IF EXISTS public.ix_personnel_orders_active;
    ALTER TABLE public.personnel_orders
      DROP COLUMN IF EXISTS deletion_reason,
      DROP COLUMN IF EXISTS deleted_by_user_id,
      DROP COLUMN IF EXISTS deleted_at;
    """)
