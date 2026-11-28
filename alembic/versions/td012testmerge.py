"""TEST-only merge of prior deployed changes with employee-history cleanup.

Copy into the TEST release's alembic/versions directory. Production uses the
ordinary td009unitclean -> td011employeehistory lineage.
"""
revision = "td012testmerge"
down_revision = ("td010testmerge", "td011employeehistory")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
