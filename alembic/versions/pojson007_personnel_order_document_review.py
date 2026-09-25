"""Append-only personnel-order document review state."""
from alembic import op

revision = "pojson007"
down_revision = "pojson006"
branch_labels = None
depends_on = None

_OLD = "'CANCEL', 'ANNUL', 'ARCHIVE', 'RESTORE', 'VOID_APPLIED', 'HARD_DELETE', 'COMPENSATE_LINK'"
_NEW = _OLD + ", 'DOCUMENT_CONFIRMED', 'DOCUMENT_REOPENED'"


def upgrade() -> None:
    op.execute("ALTER TABLE public.personnel_orders ADD COLUMN IF NOT EXISTS document_revision INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE public.personnel_orders DROP CONSTRAINT IF EXISTS chk_personnel_orders_document_revision")
    op.execute("ALTER TABLE public.personnel_orders ADD CONSTRAINT chk_personnel_orders_document_revision CHECK (document_revision >= 1)")
    op.execute("ALTER TABLE public.personnel_order_lifecycle_audit DROP CONSTRAINT IF EXISTS chk_personnel_order_lifecycle_audit_action")
    op.execute(f"ALTER TABLE public.personnel_order_lifecycle_audit ADD CONSTRAINT chk_personnel_order_lifecycle_audit_action CHECK (action IN ({_NEW}))")
    op.execute("CREATE INDEX IF NOT EXISTS ix_po_lifecycle_audit_order_document_action_created ON public.personnel_order_lifecycle_audit (order_id, action, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_po_lifecycle_audit_order_document_action_created")
    op.execute("ALTER TABLE public.personnel_order_lifecycle_audit DROP CONSTRAINT IF EXISTS chk_personnel_order_lifecycle_audit_action")
    op.execute(f"ALTER TABLE public.personnel_order_lifecycle_audit ADD CONSTRAINT chk_personnel_order_lifecycle_audit_action CHECK (action IN ({_OLD}))")
    op.execute("ALTER TABLE public.personnel_orders DROP CONSTRAINT IF EXISTS chk_personnel_orders_document_revision")
    op.execute("ALTER TABLE public.personnel_orders DROP COLUMN IF EXISTS document_revision")
