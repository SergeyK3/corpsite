"""Bind each evidence image to its required field."""
from alembic import op
from app.learning.model import screenshot_slots

revision = "learning004"
down_revision = "learning003"
branch_labels = None
depends_on = None


def upgrade():
    screenshot_slots.create(op.get_bind())


def downgrade():
    screenshot_slots.drop(op.get_bind())
