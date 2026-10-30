"""Register education references in the production Alembic chain.

Uses the same migration implementation as the isolated local rehearsal.
No personnel orders or template versions are modified or published.
"""
from alembic import op
from app.db.education_document_references_migration import upgrade as migrate

revision = "edurefs001"
down_revision = "eduprog001"
branch_labels = None
depends_on = None


def upgrade():
    migrate(op.get_bind())


def downgrade():
    raise RuntimeError("Preserve document snapshots and reference data; rollback requires a separate data audit")
