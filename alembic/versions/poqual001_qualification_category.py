"""Allow qualification-category document drafts. No data backfill."""
from alembic import op
from app.db.personnel_order_category_migration import upgrade as migrate

revision = 'poqual001'
down_revision = 'poprint001'
branch_labels = None
depends_on = None


def upgrade():
    migrate(op.get_bind())


def downgrade():
    raise RuntimeError('Removing a used order type requires an explicit data audit')
