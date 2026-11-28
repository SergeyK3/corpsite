"""Test-stand-only Alembic merge for the already deployed self-card branch.

Install this file into alembic/versions only in the test release package.
The canonical td007employee01 revision stays a child of eha006, so production
can later apply it without importing test-only self-card migrations.
"""

revision = "td008testmerge"
down_revision = ("selfcard006", "td007employee01")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
