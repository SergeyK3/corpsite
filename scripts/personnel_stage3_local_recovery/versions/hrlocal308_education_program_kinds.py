"""Editable RU/KK program kinds; existing person_education rows are not rewritten."""
from alembic import op
from app.db.education_program_kind_migration import upgrade as migrate, downgrade as undo

revision = 'hrlocal308'
down_revision = 'hrlocal307'
branch_labels = None
depends_on = None


def upgrade():
    migrate(op.get_bind())


def downgrade():
    undo(op.get_bind())
