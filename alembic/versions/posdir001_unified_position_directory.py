"""Preserve position variants and move document text into the position directory."""
from alembic import op
from app.db.position_directory_review_migration import upgrade as migrate, downgrade as rollback

revision = 'posdir001'
down_revision = 'podup001'
branch_labels = None
depends_on = None


def upgrade():
    migrate(op.get_bind())


def downgrade():
    rollback(op.get_bind())
