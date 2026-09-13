"""Persist selected import-profile provenance for canonical status evaluation."""
from alembic import op

revision = "ppr005kimport01"
down_revision = "ppr005jcanon01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      ALTER TABLE public.ppr_migration_section_status_projection
        ADD COLUMN IF NOT EXISTS source_batch_id BIGINT NULL
          REFERENCES public.hr_import_batches(batch_id) ON DELETE RESTRICT,
        ADD COLUMN IF NOT EXISTS import_profile_provenance JSONB NULL;
      CREATE INDEX IF NOT EXISTS ix_ppr_migration_status_projection_import_source
        ON public.ppr_migration_section_status_projection(source_batch_id, source_row_id)
        WHERE source_batch_id IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("""
      DROP INDEX IF EXISTS public.ix_ppr_migration_status_projection_import_source;
      ALTER TABLE public.ppr_migration_section_status_projection
        DROP COLUMN IF EXISTS import_profile_provenance,
        DROP COLUMN IF EXISTS source_batch_id;
    """)
