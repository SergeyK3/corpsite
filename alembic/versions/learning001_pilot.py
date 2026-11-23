"""Isolated learning pilot records and evidence."""
from alembic import op

revision = "learning001"
down_revision = "trn007"
branch_labels = None
depends_on = None

def upgrade():
    # Freeze the schema at revision 001. Importing today's SQLAlchemy model here
    # would also add columns owned by revisions 005 and 006.
    op.execute("""
        CREATE TABLE learning_records (
            id VARCHAR(36) PRIMARY KEY, participant_id INTEGER NOT NULL,
            unit_id INTEGER NOT NULL, application_ref VARCHAR(100) NOT NULL,
            action VARCHAR(30) NOT NULL, detail TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT learning_records_action_check
              CHECK (action IN ('opened','approved','rejected','visa_viewed'))
        );
        CREATE TABLE learning_attempts (
            id VARCHAR(36) PRIMARY KEY, participant_id INTEGER NOT NULL,
            unit_id INTEGER NOT NULL, lesson_code VARCHAR(50) NOT NULL,
            record_id VARCHAR(36) NOT NULL REFERENCES learning_records(id),
            attempt_no INTEGER NOT NULL, status VARCHAR(30) NOT NULL,
            pre_score INTEGER, pre_required BOOLEAN, score INTEGER,
            required_met BOOLEAN, reviewer_id INTEGER, reviewed_at TIMESTAMPTZ,
            review_note TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (participant_id,unit_id,lesson_code,attempt_no),
            CHECK (score IS NULL OR score BETWEEN 0 AND 5),
            CHECK (pre_score IS NULL OR pre_score BETWEEN 0 AND 5)
        );
        CREATE TABLE learning_screenshots (
            id VARCHAR(36) PRIMARY KEY,
            attempt_id VARCHAR(36) NOT NULL REFERENCES learning_attempts(id),
            participant_id INTEGER NOT NULL,
            record_id VARCHAR(36) NOT NULL REFERENCES learning_records(id),
            storage_key VARCHAR(36) NOT NULL UNIQUE, mime VARCHAR(30) NOT NULL,
            checksum VARCHAR(64) NOT NULL, bytes INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

def downgrade():
    for table in ("learning_screenshots", "learning_attempts", "learning_records"):
        op.execute(f"DROP TABLE {table}")
