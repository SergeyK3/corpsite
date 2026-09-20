"""Restore immutable Person-link journal fingerprint on databases created by old ADR-065 DDL."""
from alembic import op


revision = "aec001activecard"
down_revision = "per002eventscope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The immutable trigger forbids a backfill UPDATE.  PostgreSQL fills an ADD
    # COLUMN DEFAULT atomically, preserving historical rows without mutating
    # them; new workflow rows always provide their real SHA-256 fingerprint.
    op.execute(
        "ALTER TABLE public.personnel_identity_link_operations "
        "ADD COLUMN IF NOT EXISTS request_fingerprint TEXT NOT NULL DEFAULT ''"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.personnel_identity_link_operations "
        "DROP COLUMN IF EXISTS request_fingerprint"
    )
