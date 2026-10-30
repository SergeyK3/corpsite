"""Local document-only education type; no version or order changes."""
from alembic import op
from app.db.personnel_order_education_migration import upgrade as migrate

revision = 'hrlocal307'
down_revision = 'hrlocal306'
branch_labels = None
depends_on = None


def upgrade():
    migrate(op.get_bind())


def downgrade():
    raise RuntimeError('Removing an order type requires an explicit data audit')
