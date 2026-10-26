"""Kazakh names in the existing medical specialties directory."""
from alembic import op
from app.db.medical_specialties_schema import upgrade as migrate, downgrade as rollback

revision = "medspec001"
down_revision = "posdir001"
branch_labels = None
depends_on = None


def upgrade():
    migrate(op.get_bind())


def downgrade():
    rollback(op.get_bind())
