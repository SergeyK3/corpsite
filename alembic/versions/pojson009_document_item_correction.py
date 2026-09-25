"""Typed personnel-order document item correction."""
from alembic import op
revision="pojson009"
down_revision="pojson008"
branch_labels=None
depends_on=None
_OLD="'CANCEL', 'ANNUL', 'ARCHIVE', 'RESTORE', 'VOID_APPLIED', 'HARD_DELETE', 'COMPENSATE_LINK', 'DOCUMENT_CONFIRMED', 'DOCUMENT_REOPENED', 'HEADER_UPDATED'"
def upgrade():
    op.execute("ALTER TABLE public.personnel_order_lifecycle_audit DROP CONSTRAINT IF EXISTS chk_personnel_order_lifecycle_audit_action")
    op.execute(f"ALTER TABLE public.personnel_order_lifecycle_audit ADD CONSTRAINT chk_personnel_order_lifecycle_audit_action CHECK (action IN ({_OLD}, 'ITEM_UPDATED'))")
def downgrade():
    op.execute("ALTER TABLE public.personnel_order_lifecycle_audit DROP CONSTRAINT IF EXISTS chk_personnel_order_lifecycle_audit_action")
    op.execute(f"ALTER TABLE public.personnel_order_lifecycle_audit ADD CONSTRAINT chk_personnel_order_lifecycle_audit_action CHECK (action IN ({_OLD}))")
