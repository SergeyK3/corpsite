"""WP-TD-005 stage 2: PII-free append-only tombstones.

Revision ID: td005tomb201
Revises: td005m1v2a01
"""
from __future__ import annotations

from alembic import op


revision = "td005tomb201"
down_revision = "td005m1v2a01"
branch_labels = None
depends_on = None


_TABLES = (
    "test_personnel_deletion_record_event_tombstones",
    "test_personnel_deletion_command_tombstones",
    "test_personnel_deletion_lifecycle_tombstones",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION public.td005_tombstone_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'WP_TD_005_TOMBSTONE_APPEND_ONLY';
            END IF;
            IF NOT EXISTS (
                SELECT 1
                FROM public.test_personnel_deletion_requests request
                WHERE request.request_id = NEW.request_id
                  AND request.manifest_version = 2
                  AND request.process_type = 'APPLICANT_ONLY'
            ) THEN
                RAISE EXCEPTION 'WP_TD_005_TOMBSTONE_V2_REQUEST_REQUIRED';
            END IF;
            NEW.created_at := statement_timestamp();
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TABLE public.test_personnel_deletion_record_event_tombstones (
            tombstone_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            request_id UUID NOT NULL REFERENCES public.test_personnel_deletion_requests(request_id) ON DELETE RESTRICT,
            source_event_id BIGINT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,
            source_occurred_at TIMESTAMPTZ NOT NULL,
            actor_technical_id BIGINT NULL,
            event_payload_digest TEXT NOT NULL,
            canonical_digest TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
            CONSTRAINT ck_tpd_ret_source_id CHECK (source_event_id > 0),
            CONSTRAINT ck_tpd_ret_event_type CHECK (length(btrim(event_type)) BETWEEN 1 AND 128),
            CONSTRAINT ck_tpd_ret_actor CHECK (actor_technical_id IS NULL OR actor_technical_id > 0),
            CONSTRAINT ck_tpd_ret_payload_digest CHECK (event_payload_digest ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_tpd_ret_canonical_digest CHECK (canonical_digest ~ '^[0-9a-f]{64}$')
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.test_personnel_deletion_command_tombstones (
            tombstone_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            request_id UUID NOT NULL REFERENCES public.test_personnel_deletion_requests(request_id) ON DELETE RESTRICT,
            source_command_id TEXT NOT NULL UNIQUE,
            command_type TEXT NOT NULL,
            command_status TEXT NOT NULL,
            source_created_at TIMESTAMPTZ NOT NULL,
            source_completed_at TIMESTAMPTZ NULL,
            request_digest TEXT NOT NULL,
            result_digest TEXT NOT NULL,
            canonical_digest TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
            CONSTRAINT ck_tpd_ct_source_id CHECK (length(btrim(source_command_id)) BETWEEN 1 AND 256),
            CONSTRAINT ck_tpd_ct_command_type CHECK (length(btrim(command_type)) BETWEEN 1 AND 128),
            CONSTRAINT ck_tpd_ct_status CHECK (command_status IN ('pending', 'completed')),
            CONSTRAINT ck_tpd_ct_request_digest CHECK (request_digest ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_tpd_ct_result_digest CHECK (result_digest ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_tpd_ct_canonical_digest CHECK (canonical_digest ~ '^[0-9a-f]{64}$')
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.test_personnel_deletion_lifecycle_tombstones (
            tombstone_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            request_id UUID NOT NULL REFERENCES public.test_personnel_deletion_requests(request_id) ON DELETE RESTRICT,
            source_audit_id BIGINT NOT NULL UNIQUE,
            source_application_id BIGINT NOT NULL,
            lifecycle_action TEXT NOT NULL,
            previous_status TEXT NULL,
            new_status TEXT NULL,
            source_occurred_at TIMESTAMPTZ NOT NULL,
            actor_technical_id BIGINT NULL,
            metadata_digest TEXT NOT NULL,
            canonical_digest TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
            CONSTRAINT ck_tpd_lt_source_id CHECK (source_audit_id > 0),
            CONSTRAINT ck_tpd_lt_application_id CHECK (source_application_id > 0),
            CONSTRAINT ck_tpd_lt_action CHECK (lifecycle_action IN (
                'registered', 'intake_link_issued', 'intake_opened',
                'intake_submitted', 'intake_edited_on_behalf'
            )),
            CONSTRAINT ck_tpd_lt_actor CHECK (actor_technical_id IS NULL OR actor_technical_id > 0),
            CONSTRAINT ck_tpd_lt_metadata_digest CHECK (metadata_digest ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_tpd_lt_canonical_digest CHECK (canonical_digest ~ '^[0-9a-f]{64}$')
        )
        """
    )
    for table in _TABLES:
        op.execute(f"CREATE INDEX ix_{table}_request ON public.{table}(request_id, tombstone_id)")
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_guard
            BEFORE INSERT OR UPDATE OR DELETE ON public.{table}
            FOR EACH ROW EXECUTE FUNCTION public.td005_tombstone_guard()
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_truncate_guard
            BEFORE TRUNCATE ON public.{table}
            FOR EACH STATEMENT EXECUTE FUNCTION public.td005_tombstone_guard()
            """
        )
    op.execute(
        """
        COMMENT ON FUNCTION public.td005_tombstone_guard() IS
            'WP-TD-005 stage 2: append-only and Manifest v2 ownership guard; execution is not connected.'
        """
    )
    for table in _TABLES:
        op.execute(
            f"""COMMENT ON TABLE public.{table} IS
                'WP-TD-005 stage 2: PII-free tombstone; no source deletion or execution integration.'"""
        )


def downgrade() -> None:
    checks = " OR ".join(f"EXISTS (SELECT 1 FROM public.{table})" for table in _TABLES)
    op.execute(
        f"""
        DO $$
        BEGIN
            IF {checks} THEN
                RAISE EXCEPTION 'WP_TD_005_TOMBSTONES_PREVENT_DOWNGRADE';
            END IF;
        END $$
        """
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE public.{table}")
    op.execute("DROP FUNCTION public.td005_tombstone_guard()")
