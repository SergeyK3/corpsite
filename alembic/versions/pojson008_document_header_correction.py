"""Typed personnel-order document header correction."""
from alembic import op

revision = "pojson008"
down_revision = "pojson007"
branch_labels = None
depends_on = None

_OLD = "'CANCEL', 'ANNUL', 'ARCHIVE', 'RESTORE', 'VOID_APPLIED', 'HARD_DELETE', 'COMPENSATE_LINK', 'DOCUMENT_CONFIRMED', 'DOCUMENT_REOPENED'"
_NEW = _OLD + ", 'HEADER_UPDATED'"

def upgrade() -> None:
    op.execute("ALTER TABLE public.personnel_orders ADD COLUMN IF NOT EXISTS source_title TEXT NULL, ADD COLUMN IF NOT EXISTS source_title_locale TEXT NULL")
    op.execute("ALTER TABLE public.personnel_orders ADD CONSTRAINT chk_personnel_orders_source_title_locale CHECK (source_title_locale IS NULL OR source_title_locale IN ('kk','ru','unknown'))")
    op.execute("ALTER TABLE public.personnel_order_lifecycle_audit DROP CONSTRAINT IF EXISTS chk_personnel_order_lifecycle_audit_action")
    op.execute(f"ALTER TABLE public.personnel_order_lifecycle_audit ADD CONSTRAINT chk_personnel_order_lifecycle_audit_action CHECK (action IN ({_NEW}))")

def downgrade() -> None:
    op.execute("ALTER TABLE public.personnel_order_lifecycle_audit DROP CONSTRAINT IF EXISTS chk_personnel_order_lifecycle_audit_action")
    op.execute(f"ALTER TABLE public.personnel_order_lifecycle_audit ADD CONSTRAINT chk_personnel_order_lifecycle_audit_action CHECK (action IN ({_OLD}))")
    op.execute("ALTER TABLE public.personnel_orders DROP CONSTRAINT IF EXISTS chk_personnel_orders_source_title_locale")
    op.execute("ALTER TABLE public.personnel_orders DROP COLUMN IF EXISTS source_title_locale, DROP COLUMN IF EXISTS source_title")
