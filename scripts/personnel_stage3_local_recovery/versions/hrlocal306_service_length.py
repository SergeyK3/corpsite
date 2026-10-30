"""Local document-only service-length type; existing versions stay unchanged."""
from alembic import op
from app.db.personnel_order_service_length_migration import upgrade as migrate

revision = 'hrlocal306'
down_revision = 'hrlocal305'
branch_labels = None
depends_on = None


def upgrade():
    migrate(op.get_bind())


def downgrade():
    raise RuntimeError('Removing a used order type requires an explicit data audit')
