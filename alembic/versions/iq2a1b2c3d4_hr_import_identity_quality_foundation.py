"""IQ-2 identity-quality state and immutable review events (schema only)."""
from alembic import op

revision = "iq2a1b2c3d4"
down_revision = "ppr005hdept01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Deliberately schema-only: historical batches and rows are neither read nor written.
    op.execute("""
    ALTER TABLE public.hr_import_rows ADD CONSTRAINT uq_hr_import_rows_batch_row UNIQUE (batch_id, row_id);
    ALTER TABLE public.employees ADD CONSTRAINT uq_employees_employee_person UNIQUE (employee_id, person_id);
    CREATE TABLE public.hr_import_identity_review_events (
      event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, idempotency_key UUID NOT NULL UNIQUE,
      batch_id BIGINT NOT NULL, row_id BIGINT NOT NULL, event_type TEXT NOT NULL, resulting_state TEXT NOT NULL, reason_code TEXT NOT NULL,
      actor_type TEXT NOT NULL, actor_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT, occurred_at TIMESTAMPTZ NOT NULL,
      person_id BIGINT NULL, employee_id BIGINT NULL,
      original_iin_fingerprint TEXT NULL CHECK(original_iin_fingerprint IS NULL OR original_iin_fingerprint ~ '^[0-9a-f]{64}$'),
      entered_iin_fingerprint TEXT NULL CHECK(entered_iin_fingerprint IS NULL OR entered_iin_fingerprint ~ '^[0-9a-f]{64}$'),
      source_row_fingerprint TEXT NOT NULL CHECK(source_row_fingerprint ~ '^[0-9a-f]{64}$'),
      before_normalized_payload_fingerprint TEXT NOT NULL CHECK(before_normalized_payload_fingerprint ~ '^[0-9a-f]{64}$'),
      after_normalized_payload_fingerprint TEXT NOT NULL CHECK(after_normalized_payload_fingerprint ~ '^[0-9a-f]{64}$'),
      row_version BIGINT NOT NULL CHECK(row_version >= 1), source_version BIGINT NOT NULL CHECK(source_version >= 1),
      policy_version TEXT NOT NULL CHECK(policy_version IN ('IDENTITY_QUALITY_V1')), recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      CONSTRAINT fk_hr_import_iq_event_batch_row FOREIGN KEY(batch_id,row_id) REFERENCES public.hr_import_rows(batch_id,row_id) ON DELETE RESTRICT,
      CONSTRAINT fk_hr_import_iq_event_employee_person FOREIGN KEY(employee_id,person_id) REFERENCES public.employees(employee_id,person_id) ON DELETE RESTRICT,
      CONSTRAINT uq_hr_import_iq_event_effective UNIQUE(event_id,batch_id,row_id,source_row_fingerprint,resulting_state,reason_code),
      CONSTRAINT chk_hr_import_iq_event_decision CHECK(
        (event_type='SYSTEM_IIN_MISSING' AND actor_type='SYSTEM' AND actor_user_id IS NULL AND resulting_state='UNRESOLVED' AND reason_code='IIN_MISSING' AND person_id IS NULL AND employee_id IS NULL AND original_iin_fingerprint IS NULL AND entered_iin_fingerprint IS NULL)
        OR (event_type='SYSTEM_IIN_INVALID_FORMAT' AND actor_type='SYSTEM' AND actor_user_id IS NULL AND resulting_state='UNRESOLVED' AND reason_code='IIN_INVALID_FORMAT' AND person_id IS NULL AND employee_id IS NULL AND original_iin_fingerprint IS NOT NULL AND entered_iin_fingerprint IS NULL)
        OR (event_type='SYSTEM_IIN_UNMATCHED' AND actor_type='SYSTEM' AND actor_user_id IS NULL AND resulting_state='UNRESOLVED' AND reason_code='IIN_UNMATCHED' AND person_id IS NULL AND employee_id IS NULL AND original_iin_fingerprint IS NOT NULL AND entered_iin_fingerprint IS NULL)
        OR (event_type='IIN_CONFIRMED' AND actor_type='HR' AND actor_user_id IS NOT NULL AND resulting_state='UNRESOLVED' AND reason_code='IIN_UNMATCHED' AND person_id IS NULL AND employee_id IS NULL AND original_iin_fingerprint IS NOT NULL AND entered_iin_fingerprint IS NOT NULL)
        OR (event_type='PERSON_EMPLOYEE_LINK_CONFIRMED' AND actor_type='HR' AND actor_user_id IS NOT NULL AND resulting_state='RESOLVED' AND reason_code='IIN_CONFIRMED' AND person_id IS NOT NULL AND employee_id IS NOT NULL AND original_iin_fingerprint IS NOT NULL AND entered_iin_fingerprint IS NOT NULL)
        OR (event_type='DEFERRED' AND actor_type='HR' AND actor_user_id IS NOT NULL AND resulting_state='DEFERRED' AND reason_code='IIN_DEFERRED' AND person_id IS NULL AND employee_id IS NULL AND entered_iin_fingerprint IS NULL)
      )
    );
    CREATE INDEX ix_hr_import_identity_review_events_row_occurred ON public.hr_import_identity_review_events(batch_id,row_id,occurred_at DESC,event_id DESC);
    CREATE TABLE public.hr_import_identity_quality_states (
      state_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, batch_id BIGINT NOT NULL, row_id BIGINT NOT NULL, current_event_id BIGINT NOT NULL,
      identity_state TEXT NOT NULL, reason_code TEXT NOT NULL, person_id BIGINT NULL, employee_id BIGINT NULL,
      source_row_fingerprint TEXT NOT NULL CHECK(source_row_fingerprint ~ '^[0-9a-f]{64}$'),
      normalized_payload_fingerprint TEXT NOT NULL CHECK(normalized_payload_fingerprint ~ '^[0-9a-f]{64}$'),
      row_version BIGINT NOT NULL CHECK(row_version >= 1), source_version BIGINT NOT NULL CHECK(source_version >= 1),
      policy_version TEXT NOT NULL CHECK(policy_version IN ('IDENTITY_QUALITY_V1')), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      CONSTRAINT uq_hr_import_identity_quality_states_batch_row UNIQUE(batch_id,row_id),
      CONSTRAINT fk_hr_import_iq_state_batch_row FOREIGN KEY(batch_id,row_id) REFERENCES public.hr_import_rows(batch_id,row_id) ON DELETE RESTRICT,
      CONSTRAINT fk_hr_import_iq_state_employee_person FOREIGN KEY(employee_id,person_id) REFERENCES public.employees(employee_id,person_id) ON DELETE RESTRICT,
      CONSTRAINT fk_hr_import_iq_state_effective_event FOREIGN KEY(current_event_id,batch_id,row_id,source_row_fingerprint,identity_state,reason_code) REFERENCES public.hr_import_identity_review_events(event_id,batch_id,row_id,source_row_fingerprint,resulting_state,reason_code) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
      CONSTRAINT chk_hr_import_iq_state_reason_binding CHECK(
        (identity_state='UNRESOLVED' AND reason_code IN ('IIN_MISSING','IIN_INVALID_FORMAT','IIN_UNMATCHED') AND person_id IS NULL AND employee_id IS NULL)
        OR (identity_state='RESOLVED' AND reason_code='IIN_CONFIRMED' AND person_id IS NOT NULL AND employee_id IS NOT NULL)
        OR (identity_state='DEFERRED' AND reason_code='IIN_DEFERRED' AND person_id IS NULL AND employee_id IS NULL)
      )
    );
    ALTER TABLE public.hr_import_identity_review_events
      ADD CONSTRAINT fk_hr_import_iq_event_current_state
      FOREIGN KEY(batch_id,row_id) REFERENCES public.hr_import_identity_quality_states(batch_id,row_id)
      ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
    CREATE INDEX ix_hr_import_identity_quality_queue ON public.hr_import_identity_quality_states(batch_id,identity_state,reason_code,row_id) WHERE identity_state IN ('UNRESOLVED','DEFERRED');
    CREATE OR REPLACE FUNCTION public.assert_hr_import_iq_effective_event() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE latest public.hr_import_identity_review_events%ROWTYPE; materialized public.hr_import_identity_quality_states%ROWTYPE;
    BEGIN
      PERFORM 1 FROM public.hr_import_rows WHERE batch_id=NEW.batch_id AND row_id=NEW.row_id FOR UPDATE;
      SELECT * INTO materialized FROM public.hr_import_identity_quality_states WHERE state_id=NEW.state_id FOR UPDATE;
      SELECT * INTO latest FROM public.hr_import_identity_review_events WHERE batch_id=materialized.batch_id AND row_id=materialized.row_id AND source_row_fingerprint=materialized.source_row_fingerprint ORDER BY occurred_at DESC,event_id DESC LIMIT 1;
      IF NOT FOUND OR latest.event_id IS DISTINCT FROM materialized.current_event_id OR latest.resulting_state IS DISTINCT FROM materialized.identity_state OR latest.reason_code IS DISTINCT FROM materialized.reason_code OR latest.person_id IS DISTINCT FROM materialized.person_id OR latest.employee_id IS DISTINCT FROM materialized.employee_id THEN
        RAISE EXCEPTION 'hr_import_identity_quality_states must materialize the latest effective event';
      END IF;
      RETURN NULL;
    END; $$;
    CREATE CONSTRAINT TRIGGER trg_hr_import_iq_state_effective_event AFTER INSERT OR UPDATE ON public.hr_import_identity_quality_states DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.assert_hr_import_iq_effective_event();
    CREATE OR REPLACE FUNCTION public.assert_hr_import_iq_event_advances_state() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE current_state public.hr_import_identity_quality_states%ROWTYPE; latest public.hr_import_identity_review_events%ROWTYPE;
    BEGIN
      -- The parent-row lock serializes all identity changes for this stable batch/row key.
      PERFORM 1 FROM public.hr_import_rows WHERE batch_id=NEW.batch_id AND row_id=NEW.row_id FOR UPDATE;
      SELECT * INTO current_state FROM public.hr_import_identity_quality_states WHERE batch_id=NEW.batch_id AND row_id=NEW.row_id FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'identity review event requires current state for its batch row'; END IF;
      IF current_state.source_row_fingerprint IS DISTINCT FROM NEW.source_row_fingerprint THEN
        RAISE EXCEPTION 'identity review event source fingerprint must replace current state in the same transaction';
      END IF;
      SELECT * INTO latest FROM public.hr_import_identity_review_events WHERE batch_id=NEW.batch_id AND row_id=NEW.row_id AND source_row_fingerprint=NEW.source_row_fingerprint ORDER BY occurred_at DESC,event_id DESC LIMIT 1;
      IF latest.event_id IS DISTINCT FROM current_state.current_event_id OR latest.resulting_state IS DISTINCT FROM current_state.identity_state OR latest.reason_code IS DISTINCT FROM current_state.reason_code OR latest.person_id IS DISTINCT FROM current_state.person_id OR latest.employee_id IS DISTINCT FROM current_state.employee_id THEN
        RAISE EXCEPTION 'identity review event must advance current state in the same transaction';
      END IF;
      RETURN NULL;
    END; $$;
    CREATE CONSTRAINT TRIGGER trg_hr_import_iq_event_advances_state AFTER INSERT ON public.hr_import_identity_review_events DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.assert_hr_import_iq_event_advances_state();
    CREATE OR REPLACE FUNCTION public.prevent_hr_import_identity_review_event_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'hr_import_identity_review_events are append-only'; END; $$;
    CREATE TRIGGER trg_hr_import_identity_review_events_append_only BEFORE UPDATE OR DELETE ON public.hr_import_identity_review_events FOR EACH ROW EXECUTE FUNCTION public.prevent_hr_import_identity_review_event_mutation();
    """)


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM public.hr_import_identity_review_events) OR EXISTS(SELECT 1 FROM public.hr_import_identity_quality_states) THEN RAISE EXCEPTION 'Cannot downgrade iq2a1b2c3d4: identity-quality event or state data exists'; END IF; END $$;""")
    op.execute("ALTER TABLE public.hr_import_identity_review_events DROP CONSTRAINT fk_hr_import_iq_event_current_state")
    op.execute("DROP TRIGGER IF EXISTS trg_hr_import_identity_review_events_append_only ON public.hr_import_identity_review_events")
    op.execute("DROP TRIGGER IF EXISTS trg_hr_import_iq_event_advances_state ON public.hr_import_identity_review_events")
    op.execute("DROP TRIGGER IF EXISTS trg_hr_import_iq_state_effective_event ON public.hr_import_identity_quality_states")
    op.execute("DROP FUNCTION IF EXISTS public.prevent_hr_import_identity_review_event_mutation()")
    op.execute("DROP FUNCTION IF EXISTS public.assert_hr_import_iq_event_advances_state()")
    op.execute("DROP FUNCTION IF EXISTS public.assert_hr_import_iq_effective_event()")
    op.execute("DROP TABLE public.hr_import_identity_quality_states")
    op.execute("DROP TABLE public.hr_import_identity_review_events")
    op.execute("ALTER TABLE public.employees DROP CONSTRAINT uq_employees_employee_person")
    op.execute("ALTER TABLE public.hr_import_rows DROP CONSTRAINT uq_hr_import_rows_batch_row")
