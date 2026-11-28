"""Test-stand-only merge: preserve selfcard006 and new unit-cleanup lineage.

Copy into alembic/versions on the test release only. Production upgrades from
eha006 through td007employee01 and td009unitclean directly.
"""
revision = "td010testmerge"
down_revision = ("td008testmerge", "td009unitclean")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
