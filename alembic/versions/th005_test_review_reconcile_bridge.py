"""TEST-only merge of deployed review history and future cabinet reconciliation."""
revision = "th005testmerge"
down_revision = ("th003testmerge", "th004cabinetreconcile")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
