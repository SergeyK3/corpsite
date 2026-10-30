"""Allow document-only personal-data orders."""
from alembic import op
from app.db.personnel_order_personal_data_migration import upgrade as migrate,downgrade as undo
revision='hrlocal310'
down_revision='hrlocal309'
branch_labels=None
depends_on=None
def upgrade():migrate(op.get_bind())
def downgrade():undo(op.get_bind())
