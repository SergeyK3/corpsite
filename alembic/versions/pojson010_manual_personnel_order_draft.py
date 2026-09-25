"""Allow explicit manual personnel-order drafts."""
from alembic import op

revision = "pojson010"
down_revision = "pojson009"
branch_labels = None
depends_on = None

_OLD = "'PAPER', 'DIGITAL'"
_NEW = "'PAPER', 'DIGITAL', 'MANUAL'"


def upgrade() -> None:
    op.execute("ALTER TABLE public.personnel_orders DROP CONSTRAINT IF EXISTS chk_personnel_orders_source_mode")
    op.execute(f"ALTER TABLE public.personnel_orders ADD CONSTRAINT chk_personnel_orders_source_mode CHECK (source_mode IN ({_NEW}))")


def downgrade() -> None:
    op.execute("ALTER TABLE public.personnel_orders DROP CONSTRAINT IF EXISTS chk_personnel_orders_source_mode")
    op.execute(f"ALTER TABLE public.personnel_orders ADD CONSTRAINT chk_personnel_orders_source_mode CHECK (source_mode IN ({_OLD}))")
