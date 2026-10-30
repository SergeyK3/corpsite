"""Independent education levels and bilingual legacy document kinds."""
from alembic import op
from app.db.education_document_references_migration import upgrade as migrate,downgrade as undo

revision='hrlocal309'
down_revision='hrlocal308'
branch_labels=None
depends_on=None

def upgrade(): migrate(op.get_bind())
def downgrade(): undo(op.get_bind())
