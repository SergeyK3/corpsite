"""Register personal data orders in the production Alembic chain.

Uses the same migration implementation as the isolated local rehearsal.
No personnel orders or template versions are modified or published.
"""
from alembic import op
from app.db.personnel_order_personal_data_migration import upgrade as migrate

revision = "popdata001"
down_revision = "edurefs001"
branch_labels = None
depends_on = None


def upgrade():
    migrate(op.get_bind())


def downgrade():
    raise RuntimeError("Preserve document snapshots and reference data; rollback requires a separate data audit")
