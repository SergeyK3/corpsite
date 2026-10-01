"""Extend order review staging for unconfirmed vacation-register evidence."""
from alembic import op

revision = "dxe002vacation01"
down_revision = "dxe001framework01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.personnel_order_import_review_records ALTER COLUMN employee_id DROP NOT NULL")
    op.execute("ALTER TABLE public.personnel_order_import_review_records ALTER COLUMN order_date DROP NOT NULL")
    op.execute("""
        ALTER TABLE public.personnel_order_import_review_records
          ADD COLUMN schema_version TEXT NULL,
          ADD COLUMN source_file_sha256 TEXT NULL,
          ADD COLUMN source_row_id TEXT NULL,
          ADD COLUMN block_number TEXT NULL,
          ADD COLUMN event_number TEXT NULL,
          ADD COLUMN source_values JSONB NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN normalized_values JSONB NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN proposed_values JSONB NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN hr_correction JSONB NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN hr_reviewed BOOLEAN NOT NULL DEFAULT FALSE,
          ADD COLUMN hr_decision TEXT NULL,
          ADD COLUMN hr_comment TEXT NULL,
          ADD COLUMN block_reason TEXT NULL,
          ADD COLUMN version INTEGER NOT NULL DEFAULT 1,
          ADD CONSTRAINT chk_personnel_order_review_version CHECK (version > 0),
          ADD CONSTRAINT chk_personnel_order_review_source_sha CHECK (source_file_sha256 IS NULL OR source_file_sha256 ~ '^[0-9a-f]{64}$');
        CREATE INDEX ix_personnel_order_import_review_source_row
          ON public.personnel_order_import_review_records(source_file_sha256, source_row_id);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_personnel_order_import_review_source_row")
    op.execute("""
        ALTER TABLE public.personnel_order_import_review_records
          DROP CONSTRAINT IF EXISTS chk_personnel_order_review_source_sha,
          DROP CONSTRAINT IF EXISTS chk_personnel_order_review_version,
          DROP COLUMN IF EXISTS version,
          DROP COLUMN IF EXISTS block_reason,
          DROP COLUMN IF EXISTS hr_comment,
          DROP COLUMN IF EXISTS hr_decision,
          DROP COLUMN IF EXISTS hr_reviewed,
          DROP COLUMN IF EXISTS hr_correction,
          DROP COLUMN IF EXISTS proposed_values,
          DROP COLUMN IF EXISTS normalized_values,
          DROP COLUMN IF EXISTS source_values,
          DROP COLUMN IF EXISTS event_number,
          DROP COLUMN IF EXISTS block_number,
          DROP COLUMN IF EXISTS source_row_id,
          DROP COLUMN IF EXISTS source_file_sha256,
          DROP COLUMN IF EXISTS schema_version;
    """)
    # Cannot restore NOT NULL while unlinked review rows exist; downgrade is intentionally blocked in that case.
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM public.personnel_order_import_review_records WHERE employee_id IS NULL) THEN
        RAISE EXCEPTION 'cannot downgrade dxe002 while unlinked vacation review records exist';
      END IF;
    END $$;
    ALTER TABLE public.personnel_order_import_review_records ALTER COLUMN employee_id SET NOT NULL;
    ALTER TABLE public.personnel_order_import_review_records ALTER COLUMN order_date SET NOT NULL;
    """)
