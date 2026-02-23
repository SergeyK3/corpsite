"""add assignment_scope_t enum"""

from alembic import op

revision = "b17f7f69c7d5"
down_revision = "02b0d99063cd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'assignment_scope_t') THEN
            CREATE TYPE assignment_scope_t AS ENUM ('dept','unit','group','user','role');
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'assignment_scope_t') THEN
            DROP TYPE assignment_scope_t;
          END IF;
        END $$;
        """
    )