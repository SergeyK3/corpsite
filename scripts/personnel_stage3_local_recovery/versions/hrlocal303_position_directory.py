"""Apply the same unified directory schema to the verified local branch."""
from alembic import op
from app.db.position_directory_migration import upgrade as migrate, downgrade as rollback

revision = 'hrlocal303'
down_revision = 'hrlocal302'
branch_labels = None
depends_on = None


def upgrade():
    migrate(op.get_bind())


def downgrade():
    rollback(op.get_bind())
