"""Add editable pension details and append-only fact tombstones.

The original import row remains the source of the human-readable note.  This
migration only extends the canonical, versioned status-fact model used by the
PPR card.
"""
from alembic import op


revision = "ppr005qnotedetails01"
down_revision = "ppr005pcategoryfix01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.person_status_facts
          ADD COLUMN IF NOT EXISTS pension_kind TEXT NULL,
          ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;

        ALTER TABLE public.person_status_facts
          DROP CONSTRAINT IF EXISTS chk_person_status_facts_pension_kind;
        ALTER TABLE public.person_status_facts
          ADD CONSTRAINT chk_person_status_facts_pension_kind
          CHECK (pension_kind IS NULL OR pension_kind IN ('AGE', 'SERVICE'));

        DROP INDEX IF EXISTS public.uq_person_status_facts_source_kind_version;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_person_status_facts_source_kind_version
          ON public.person_status_facts(source_row_id, fact_kind, version, source_fingerprint);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM public.person_status_facts
            WHERE pension_kind IS NOT NULL OR is_deleted
          ) THEN
            RAISE EXCEPTION 'Cannot downgrade ppr005qnotedetails01: editable note facts exist';
          END IF;
        END $$;
        DROP INDEX IF EXISTS public.uq_person_status_facts_source_kind_version;
        CREATE UNIQUE INDEX uq_person_status_facts_source_kind_version
          ON public.person_status_facts(source_row_id, fact_kind, version);
        ALTER TABLE public.person_status_facts
          DROP CONSTRAINT IF EXISTS chk_person_status_facts_pension_kind,
          DROP COLUMN IF EXISTS is_deleted,
          DROP COLUMN IF EXISTS pension_kind;
        """
    )
