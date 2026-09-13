"""Index deterministic import-card IIN lookup used by status projection."""
from alembic import op


revision = "ppr005nimportiinidx01"
down_revision = "ppr005madditionalfix01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE INDEX IF NOT EXISTS ix_hr_import_rows_normalized_iin_digits
      ON public.hr_import_rows
      ((regexp_replace(COALESCE(normalized_payload->>'iin', ''), '[^0-9]', '', 'g')));
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_hr_import_rows_normalized_iin_digits;")
