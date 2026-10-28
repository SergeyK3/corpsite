"""Fixed bilingual medical qualification directory."""
from alembic import op
from app.db.medical_qualification_categories_schema import upgrade as migrate, downgrade as rollback

revision = "medqual001"
down_revision = "poqual001"
branch_labels = None
depends_on = None


def upgrade():
    migrate(op.get_bind())


def downgrade():
    rollback(op.get_bind())
