"""Isolated fictional application bound to one approval attempt."""
from alembic import op
from app.learning.model import exercise_applications

revision = "learning003"
down_revision = "learning002"
branch_labels = None
depends_on = None


def upgrade():
    exercise_applications.create(op.get_bind())


def downgrade():
    exercise_applications.drop(op.get_bind())
