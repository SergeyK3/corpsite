"""Store reviewer criterion results for each learning attempt."""
from alembic import op
from app.learning.model import criterion_results

revision = "learning002"
down_revision = "learning001"
branch_labels = None
depends_on = None


def upgrade():
    criterion_results.create(op.get_bind())


def downgrade():
    criterion_results.drop(op.get_bind())
