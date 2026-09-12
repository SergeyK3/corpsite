"""Append-only disability and pension facts from HR-import notes.

The migration is schema-only.  Processing the current control-list batch is
performed explicitly by the importer service, never as a migration side
effect.
"""
from alembic import op


revision = "ppr005iadd01"
down_revision = "iq2a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.person_status_facts (
          status_fact_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          person_id BIGINT NOT NULL REFERENCES public.persons(person_id) ON DELETE RESTRICT,
          employee_context_id BIGINT NULL REFERENCES public.employees(employee_id) ON DELETE SET NULL,
          fact_kind TEXT NOT NULL,
          effective_date DATE NULL,
          disability_group TEXT NULL,
          icd10_code TEXT NULL,
          review_status TEXT NOT NULL,
          review_reason TEXT NULL,
          source_batch_id BIGINT NOT NULL REFERENCES public.hr_import_batches(batch_id) ON DELETE RESTRICT,
          source_row_id BIGINT NOT NULL REFERENCES public.hr_import_rows(row_id) ON DELETE RESTRICT,
          source_policy_version TEXT NOT NULL,
          source_fingerprint TEXT NOT NULL,
          supersedes_fact_id BIGINT NULL REFERENCES public.person_status_facts(status_fact_id) ON DELETE RESTRICT,
          version BIGINT NOT NULL DEFAULT 1,
          correction_reason TEXT NULL,
          created_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT chk_person_status_facts_kind CHECK (fact_kind IN ('DISABILITY', 'PENSION')),
          CONSTRAINT chk_person_status_facts_review_status CHECK (review_status IN ('AUTO_READY', 'REVIEW_REQUIRED')),
          CONSTRAINT chk_person_status_facts_disability_group CHECK (disability_group IS NULL OR disability_group IN ('I', 'II', 'III')),
          CONSTRAINT chk_person_status_facts_icd10 CHECK (icd10_code IS NULL OR icd10_code ~ '^[A-TV-Z][0-9]{2}(\\.[0-9A-Z]{1,4})?$'),
          CONSTRAINT chk_person_status_facts_pension_shape CHECK ((fact_kind = 'DISABILITY') OR (disability_group IS NULL AND icd10_code IS NULL))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_person_status_facts_source_kind_version
          ON public.person_status_facts(source_row_id, fact_kind, version);
        CREATE INDEX IF NOT EXISTS ix_person_status_facts_person_kind
          ON public.person_status_facts(person_id, fact_kind, version);
        CREATE INDEX IF NOT EXISTS ix_person_status_facts_source_row
          ON public.person_status_facts(source_row_id);
        CREATE OR REPLACE FUNCTION public.prevent_person_status_fact_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'person_status_facts are append-only';
        END;
        $$;
        DROP TRIGGER IF EXISTS trg_person_status_facts_append_only ON public.person_status_facts;
        CREATE TRIGGER trg_person_status_facts_append_only
          BEFORE UPDATE OR DELETE ON public.person_status_facts
          FOR EACH ROW EXECUTE FUNCTION public.prevent_person_status_fact_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM public.person_status_facts) THEN
            RAISE EXCEPTION 'Cannot downgrade ppr005iadd01: person status facts exist';
          END IF;
        END $$;
        DROP TRIGGER IF EXISTS trg_person_status_facts_append_only ON public.person_status_facts;
        DROP FUNCTION IF EXISTS public.prevent_person_status_fact_mutation();
        DROP TABLE public.person_status_facts;
        """
    )
