"""Opt-in local branch counterpart of poqual001; no row changes."""
from alembic import op
from app.db.personnel_order_category_migration import upgrade as migrate

revision = 'hrlocal305'
down_revision = 'hrlocal304'
branch_labels = None
depends_on = None


def upgrade():
    migrate(op.get_bind())


def downgrade():
    raise RuntimeError('Removing a used order type requires an explicit data audit')
