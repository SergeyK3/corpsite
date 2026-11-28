"""Test-only merge of installed fixes with archive return history."""

revision = "td013ooreturnmerge"
down_revision = ("td012testmerge", "ooar001return")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
