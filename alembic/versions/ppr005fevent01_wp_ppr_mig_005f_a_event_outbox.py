"""WP-PPR-MIG-005F-A immutable correction events and targeted projection outbox."""
from alembic import op

revision = "ppr005fevent01"
down_revision = "ppr005cread01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE public.ppr_section_manual_correction_events (
      event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      event_type TEXT NOT NULL CHECK (event_type = 'PPR_SECTION_MANUAL_CORRECTED'),
      idempotency_key UUID NOT NULL UNIQUE,
      actor_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
      person_id BIGINT NOT NULL REFERENCES public.persons(person_id) ON DELETE RESTRICT,
      employee_context_id BIGINT NULL REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
      universe_id BIGINT NOT NULL REFERENCES public.ppr_migration_status_universes(universe_id) ON DELETE RESTRICT,
      cohort_run_id BIGINT NOT NULL REFERENCES public.ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT,
      section_code TEXT NOT NULL CHECK (section_code IN ('general','education','training')),
      origin_status TEXT NOT NULL CHECK (origin_status IN ('REVIEW_REQUIRED','ERROR')),
      origin_reason_code TEXT NOT NULL CHECK (origin_reason_code IN (
        'SOURCE_FRAGMENT_UNREVIEWED','CONFLICT_NAME_PARSE','CONFLICT_CANONICAL_VALUE',
        'CONFLICT_EDUCATION_IDENTITY','CONFLICT_TRAINING_IDENTITY','RUN_EXECUTION_ERROR',
        'RUN_ACCEPTANCE_PAUSED','RUN_PARTICIPANT_ERROR'
      )),
      stage_run_id BIGINT NULL REFERENCES public.ppr_stage_runs(stage_run_id) ON DELETE RESTRICT,
      stage1_run_id BIGINT NULL REFERENCES public.ppr_stage1_general_runs(stage1_run_id) ON DELETE RESTRICT,
      stage_participant_id BIGINT NULL REFERENCES public.ppr_stage_run_participants(stage_run_participant_id) ON DELETE RESTRICT,
      stage1_participant_id BIGINT NULL REFERENCES public.ppr_stage1_general_participants(stage1_participant_id) ON DELETE RESTRICT,
      pmf_run_id BIGINT NULL REFERENCES public.personnel_migration_runs(run_id) ON DELETE RESTRICT,
      pmf_item_id BIGINT NULL REFERENCES public.personnel_migration_items(item_id) ON DELETE RESTRICT,
      evidence_event_id BIGINT NULL REFERENCES public.personnel_record_events(event_id) ON DELETE RESTRICT,
      before_source_fingerprint TEXT NOT NULL CHECK (before_source_fingerprint ~ '^[0-9a-f]{64}$'),
      before_target_fingerprint TEXT NOT NULL CHECK (before_target_fingerprint ~ '^[0-9a-f]{64}$'),
      before_binding_fingerprint TEXT NOT NULL CHECK (before_binding_fingerprint ~ '^[0-9a-f]{64}$'),
      after_source_fingerprint TEXT NOT NULL CHECK (after_source_fingerprint ~ '^[0-9a-f]{64}$'),
      after_target_fingerprint TEXT NOT NULL CHECK (after_target_fingerprint ~ '^[0-9a-f]{64}$'),
      after_binding_fingerprint TEXT NOT NULL CHECK (after_binding_fingerprint ~ '^[0-9a-f]{64}$'),
      policy_version TEXT NOT NULL CHECK (length(trim(policy_version)) > 0),
      optimistic_version BIGINT NOT NULL CHECK (optimistic_version >= 1),
      occurred_at TIMESTAMPTZ NOT NULL,
      recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_ppr_section_manual_correction_events_target
      ON public.ppr_section_manual_correction_events(universe_id, person_id, section_code, recorded_at DESC);
    CREATE INDEX ix_ppr_section_manual_correction_events_actor
      ON public.ppr_section_manual_correction_events(actor_user_id, recorded_at DESC);

    CREATE TABLE public.ppr_migration_projection_outbox (
      outbox_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      event_id BIGINT NOT NULL UNIQUE REFERENCES public.ppr_section_manual_correction_events(event_id) ON DELETE RESTRICT,
      idempotency_key UUID NOT NULL UNIQUE,
      universe_id BIGINT NOT NULL REFERENCES public.ppr_migration_status_universes(universe_id) ON DELETE RESTRICT,
      person_id BIGINT NOT NULL REFERENCES public.persons(person_id) ON DELETE RESTRICT,
      section_code TEXT NOT NULL CHECK (section_code IN ('general','education','training')),
      job_kind TEXT NOT NULL CHECK (job_kind IN ('TARGETED_RECALCULATE','TARGETED_INVALIDATE','POLICY_BATCH_INVALIDATE')),
      state_code TEXT NOT NULL DEFAULT 'PENDING' CHECK (state_code IN ('PENDING','PROCESSING','RETRY','COMPLETED','DEAD')),
      attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
      next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      claimed_at TIMESTAMPTZ NULL,
      claimed_by TEXT NULL CHECK (claimed_by IS NULL OR length(trim(claimed_by)) > 0),
      last_error_code TEXT NULL CHECK (last_error_code IS NULL OR last_error_code IN ('PROJECTOR_TRANSIENT','PROJECTOR_CONFLICT','PROJECTOR_INTERNAL','LOCK_TIMEOUT','FINGERPRINT_MISMATCH')),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      processed_at TIMESTAMPTZ NULL,
      CHECK (
        (state_code = 'PROCESSING' AND claimed_at IS NOT NULL AND claimed_by IS NOT NULL AND processed_at IS NULL)
        OR (state_code IN ('PENDING','RETRY') AND processed_at IS NULL)
        OR (state_code IN ('COMPLETED','DEAD') AND processed_at IS NOT NULL)
      )
    );
    CREATE INDEX ix_ppr_migration_projection_outbox_ready
      ON public.ppr_migration_projection_outbox(next_attempt_at, outbox_id)
      WHERE state_code IN ('PENDING','RETRY');
    CREATE INDEX ix_ppr_migration_projection_outbox_target
      ON public.ppr_migration_projection_outbox(universe_id, person_id, section_code, state_code);

    CREATE OR REPLACE FUNCTION public.prevent_ppr_section_manual_correction_event_mutation()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      RAISE EXCEPTION 'ppr_section_manual_correction_events are immutable';
    END;
    $$;
    CREATE TRIGGER trg_ppr_section_manual_correction_events_immutable
      BEFORE UPDATE OR DELETE ON public.ppr_section_manual_correction_events
      FOR EACH ROW EXECUTE FUNCTION public.prevent_ppr_section_manual_correction_event_mutation();

    CREATE OR REPLACE FUNCTION public.prevent_ppr_migration_projection_outbox_identity_mutation()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.event_id IS DISTINCT FROM OLD.event_id
         OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
         OR NEW.universe_id IS DISTINCT FROM OLD.universe_id
         OR NEW.person_id IS DISTINCT FROM OLD.person_id
         OR NEW.section_code IS DISTINCT FROM OLD.section_code
         OR NEW.job_kind IS DISTINCT FROM OLD.job_kind
         OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'ppr_migration_projection_outbox identity is immutable';
      END IF;
      RETURN NEW;
    END;
    $$;
    CREATE TRIGGER trg_ppr_migration_projection_outbox_identity_immutable
      BEFORE UPDATE ON public.ppr_migration_projection_outbox
      FOR EACH ROW EXECUTE FUNCTION public.prevent_ppr_migration_projection_outbox_identity_mutation();
    """)


def downgrade() -> None:
    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM public.ppr_section_manual_correction_events)
         OR EXISTS (SELECT 1 FROM public.ppr_migration_projection_outbox) THEN
        RAISE EXCEPTION 'Cannot downgrade ppr005fevent01: correction event or projection outbox data exists';
      END IF;
    END
    $$;
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_ppr_section_manual_correction_events_immutable ON public.ppr_section_manual_correction_events")
    op.execute("DROP FUNCTION IF EXISTS public.prevent_ppr_section_manual_correction_event_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_ppr_migration_projection_outbox_identity_immutable ON public.ppr_migration_projection_outbox")
    op.execute("DROP FUNCTION IF EXISTS public.prevent_ppr_migration_projection_outbox_identity_mutation()")
    op.execute("DROP TABLE public.ppr_migration_projection_outbox")
    op.execute("DROP TABLE public.ppr_section_manual_correction_events")
