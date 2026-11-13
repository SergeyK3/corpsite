"""Fixed personnel position types and conservative initial position mapping."""
from alembic import op
from app.db.position_type_migration import upgrade as migrate

revision = "ptype001"
down_revision = "asst005"
branch_labels = None
depends_on = None


def upgrade():
    migrate(op.get_bind())


def downgrade():
    raise RuntimeError("Position type rollback needs a data-preserving plan")
