"""WP-TD-005 stage 5: transactional applicant-only execution state contract.

Revision ID: td005exec501
Revises: td005audit401
"""
from __future__ import annotations

from alembic import op


revision = "td005exec501"
down_revision = "td005audit401"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        r"""
        DO $migration$
        DECLARE function_sql TEXT;
        BEGIN
            function_sql := pg_get_functiondef(
                'public.td005_execute_projection_valid(jsonb,uuid,bigint,text,timestamptz,text)'::regprocedure
            );
            function_sql := replace(
                function_sql,
                '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
                '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            );
            EXECUTE function_sql;
        END
        $migration$
        """
    )
    # PPR command_id is caller supplied and can contain PII.  Execution uses a
    # server-generated identity and stores only a digest of the caller value.
    op.execute(
        "ALTER TABLE public.ppr_command_executions "
        "ADD COLUMN command_execution_id BIGINT GENERATED ALWAYS AS IDENTITY"
    )
    op.execute(
        "ALTER TABLE public.ppr_command_executions "
        "ADD CONSTRAINT uq_ppr_command_execution_id UNIQUE (command_execution_id)"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "ADD COLUMN source_command_execution_id BIGINT"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "ADD COLUMN source_reference_digest TEXT"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.test_personnel_deletion_command_tombstones) THEN
                RAISE EXCEPTION 'WP_TD_005_LEGACY_COMMAND_TOMBSTONES_PREVENT_UPGRADE';
            END IF;
        END $$
        """
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "ALTER COLUMN source_command_execution_id SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "ALTER COLUMN source_reference_digest SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "ADD CONSTRAINT uq_tpd_ct_source_execution UNIQUE (source_command_execution_id)"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "ADD CONSTRAINT ck_tpd_ct_source_execution CHECK (source_command_execution_id > 0)"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "ADD CONSTRAINT ck_tpd_ct_source_reference_digest "
        "CHECK (source_reference_digest ~ '^[0-9a-f]{64}$')"
    )
    op.execute(
        """
        DO $$
        DECLARE unique_name TEXT;
        BEGIN
            SELECT constraint_def.conname INTO unique_name
            FROM pg_catalog.pg_constraint constraint_def
            WHERE constraint_def.conrelid=
                    'public.test_personnel_deletion_command_tombstones'::regclass
              AND constraint_def.contype='u'
              AND pg_get_constraintdef(constraint_def.oid)='UNIQUE (source_command_id)';
            IF unique_name IS NULL THEN
                RAISE EXCEPTION 'WP_TD_005_COMMAND_SOURCE_UNIQUE_CONSTRAINT_MISSING';
            END IF;
            EXECUTE format(
                'ALTER TABLE public.test_personnel_deletion_command_tombstones DROP CONSTRAINT %I',
                unique_name
            );
        END $$
        """
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "DROP CONSTRAINT ck_tpd_ct_source_id"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "DROP COLUMN source_command_id"
    )

    op.execute(
        """
        CREATE TABLE public.test_personnel_deletion_execution_attempts (
            attempt_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            request_id UUID NOT NULL REFERENCES public.test_personnel_deletion_requests(request_id) ON DELETE RESTRICT,
            executor_user_id BIGINT NOT NULL,
            idempotency_key UUID NOT NULL,
            command_payload_hash TEXT NOT NULL,
            event_type TEXT NOT NULL,
            result_code TEXT NULL,
            error_code TEXT NULL,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
            CONSTRAINT uq_tpd_execution_attempt_event UNIQUE (idempotency_key,event_type),
            CONSTRAINT ck_tpd_execution_attempt_executor CHECK (executor_user_id > 0),
            CONSTRAINT ck_tpd_execution_attempt_hash CHECK (command_payload_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_tpd_execution_attempt_type CHECK (event_type IN ('INTENT','RESULT')),
            CONSTRAINT ck_tpd_execution_attempt_result CHECK (
                (event_type='INTENT' AND result_code IS NULL AND error_code IS NULL)
                OR (event_type='RESULT' AND result_code ~ '^TD_[A-Z0-9_]{1,124}$'
                    AND (error_code IS NULL OR error_code ~ '^TD_[A-Z0-9_]{1,124}$'))
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_tpd_execution_attempt_request "
        "ON public.test_personnel_deletion_execution_attempts(request_id,occurred_at,attempt_event_id)"
    )
    op.execute(
        """
        CREATE TRIGGER trg_tpd_execution_attempt_append_only
        BEFORE UPDATE OR DELETE ON public.test_personnel_deletion_execution_attempts
        FOR EACH ROW EXECUTE FUNCTION public.td002_reject_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_tpd_execution_attempt_truncate_guard
        BEFORE TRUNCATE ON public.test_personnel_deletion_execution_attempts
        FOR EACH STATEMENT EXECUTE FUNCTION public.td002_reject_mutation()
        """
    )
    op.execute("ALTER TABLE public.test_personnel_deletion_requests DROP CONSTRAINT ck_tpdr_status")
    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_requests
        ADD CONSTRAINT ck_tpdr_status CHECK (status IN (
            'DRAFT', 'PENDING_HR_APPROVAL', 'APPROVED', 'REJECTED',
            'REAPPROVAL_REQUIRED', 'CANCELLED', 'EXPIRED', 'COMPLETED'
        ))
        """
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_history "
        "DROP CONSTRAINT ck_tpdh_execute_contract"
    )
    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_history
        ADD CONSTRAINT ck_tpdh_execute_contract CHECK (
            action <> 'EXECUTE' OR (
                permission_code = 'TEST_PERSONNEL_DELETION_EXECUTE'
                AND actor_role_code = 'ADMIN'
                AND comment IS NULL
                AND old_status = 'APPROVED'
                AND (
                    (new_status = 'APPROVED' AND old_version = new_version)
                    OR (new_status IN ('COMPLETED', 'REAPPROVAL_REQUIRED')
                        AND new_version = old_version + 1)
                )
                AND public.td005_execute_projection_valid(
                    result_projection, request_id, actor_user_id,
                    idempotency_key, occurred_at, result_code
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.td005_execute_audit_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.action='EXECUTE' AND NOT (
                NEW.permission_code='TEST_PERSONNEL_DELETION_EXECUTE'
                AND NEW.actor_role_code='ADMIN'
                AND NEW.comment IS NULL
                AND NEW.old_status='APPROVED'
                AND (
                    (NEW.new_status='APPROVED' AND NEW.old_version=NEW.new_version)
                    OR (NEW.new_status IN ('COMPLETED','REAPPROVAL_REQUIRED')
                        AND NEW.new_version=NEW.old_version+1)
                )
                AND public.td005_execute_projection_valid(
                    NEW.result_projection, NEW.request_id, NEW.actor_user_id,
                    NEW.idempotency_key, NEW.occurred_at, NEW.result_code
                )
            ) THEN
                RAISE EXCEPTION 'WP_TD_005_EXECUTE_AUDIT_CONTRACT_INVALID';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.td005_lock_logical_person_writer() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            candidate JSONB := CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
            logical_person_id BIGINT;
        BEGIN
            logical_person_id := NULLIF(candidate->>'person_id','')::bigint;
            IF logical_person_id IS NOT NULL THEN
                PERFORM pg_advisory_xact_lock(
                    hashtextextended('WP-TD-005:PERSON:' || logical_person_id::text, 0)
                );
                IF TG_OP <> 'DELETE' AND NOT EXISTS (
                    SELECT 1 FROM public.persons WHERE person_id=logical_person_id
                ) THEN
                    RAISE EXCEPTION 'WP_TD_005_LOGICAL_PERSON_TARGET_MISSING';
                END IF;
            END IF;
            RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
        END;
        $$
        """
    )
    for table in ("personnel", "contacts", "contact_access", "key_contacts", "org_unit_key_staff"):
        op.execute(
            f"""DO $$ BEGIN
            IF to_regclass('public.{table}') IS NOT NULL THEN
                EXECUTE 'CREATE TRIGGER trg_{table}_td005_person_lock
                    BEFORE INSERT OR UPDATE OR DELETE ON public.{table}
                    FOR EACH ROW EXECUTE FUNCTION public.td005_lock_logical_person_writer()';
            END IF;
            END $$"""
        )
    op.execute(
        """
        CREATE FUNCTION public.td005_lock_person_access_grant_writer() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            candidate JSONB := CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
            logical_person_id BIGINT;
        BEGIN
            IF candidate->>'target_type'='PERSON' THEN
                logical_person_id := NULLIF(candidate->>'target_id','')::bigint;
                PERFORM pg_advisory_xact_lock(
                    hashtextextended('WP-TD-005:PERSON:' || logical_person_id::text, 0)
                );
                IF TG_OP <> 'DELETE' AND NOT EXISTS (
                    SELECT 1 FROM public.persons WHERE person_id=logical_person_id
                ) THEN
                    RAISE EXCEPTION 'WP_TD_005_LOGICAL_PERSON_TARGET_MISSING';
                END IF;
            END IF;
            RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
        END;
        $$
        """
    )
    op.execute(
        """CREATE TRIGGER trg_access_grants_td005_person_lock
        BEFORE INSERT OR UPDATE OR DELETE ON public.access_grants
        FOR EACH ROW EXECUTE FUNCTION public.td005_lock_person_access_grant_writer()"""
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.test_personnel_deletion_requests
                       WHERE status='COMPLETED')
               OR EXISTS (SELECT 1 FROM public.test_personnel_deletion_history
                          WHERE action='EXECUTE' AND (new_status<>'APPROVED' OR old_version<>new_version))
               OR EXISTS (SELECT 1 FROM public.test_personnel_deletion_execution_attempts)
               OR EXISTS (SELECT 1 FROM public.test_personnel_deletion_command_tombstones) THEN
                RAISE EXCEPTION 'WP_TD_005_EXECUTION_STATE_PREVENTS_DOWNGRADE';
            END IF;
        END $$
        """
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_history "
        "DROP CONSTRAINT ck_tpdh_execute_contract"
    )
    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_history
        ADD CONSTRAINT ck_tpdh_execute_contract CHECK (
            action <> 'EXECUTE' OR (
                permission_code = 'TEST_PERSONNEL_DELETION_EXECUTE'
                AND actor_role_code = 'ADMIN'
                AND comment IS NULL
                AND old_status = 'APPROVED'
                AND new_status = 'APPROVED'
                AND old_version = new_version
                AND public.td005_execute_projection_valid(
                    result_projection, request_id, actor_user_id,
                    idempotency_key, occurred_at, result_code
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.td005_execute_audit_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.action='EXECUTE' AND NOT (
                NEW.permission_code='TEST_PERSONNEL_DELETION_EXECUTE'
                AND NEW.actor_role_code='ADMIN'
                AND NEW.comment IS NULL
                AND NEW.old_status='APPROVED'
                AND NEW.new_status='APPROVED'
                AND NEW.old_version=NEW.new_version
                AND public.td005_execute_projection_valid(
                    NEW.result_projection, NEW.request_id, NEW.actor_user_id,
                    NEW.idempotency_key, NEW.occurred_at, NEW.result_code
                )
            ) THEN
                RAISE EXCEPTION 'WP_TD_005_EXECUTE_AUDIT_CONTRACT_INVALID';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute("DROP TRIGGER trg_access_grants_td005_person_lock ON public.access_grants")
    op.execute("DROP FUNCTION public.td005_lock_person_access_grant_writer()")
    for table in ("org_unit_key_staff", "key_contacts", "contact_access", "contacts", "personnel"):
        op.execute(f"""DO $$ BEGIN
            IF to_regclass('public.{table}') IS NOT NULL THEN
                EXECUTE 'DROP TRIGGER trg_{table}_td005_person_lock ON public.{table}';
            END IF;
            END $$""")
    op.execute("DROP FUNCTION public.td005_lock_logical_person_writer()")
    op.execute("DROP TABLE public.test_personnel_deletion_execution_attempts")
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "ADD COLUMN source_command_id TEXT"
    )
    op.execute(
        "UPDATE public.test_personnel_deletion_command_tombstones tombstone "
        "SET source_command_id=command.command_id FROM public.ppr_command_executions command "
        "WHERE command.command_execution_id=tombstone.source_command_execution_id"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "ALTER COLUMN source_command_id SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "ADD CONSTRAINT uq_tpd_ct_source_command "
        "UNIQUE (source_command_id)"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "ADD CONSTRAINT ck_tpd_ct_source_id CHECK (length(btrim(source_command_id)) BETWEEN 1 AND 256)"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "DROP CONSTRAINT uq_tpd_ct_source_execution"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "DROP CONSTRAINT ck_tpd_ct_source_execution"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "DROP CONSTRAINT ck_tpd_ct_source_reference_digest"
    )
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_command_tombstones "
        "DROP COLUMN source_reference_digest, DROP COLUMN source_command_execution_id"
    )
    op.execute(
        "ALTER TABLE public.ppr_command_executions "
        "DROP CONSTRAINT uq_ppr_command_execution_id, DROP COLUMN command_execution_id"
    )
    op.execute(
        r"""
        DO $migration$
        DECLARE function_sql TEXT;
        BEGIN
            function_sql := pg_get_functiondef(
                'public.td005_execute_projection_valid(jsonb,uuid,bigint,text,timestamptz,text)'::regprocedure
            );
            function_sql := replace(
                function_sql,
                '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
                '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
            );
            EXECUTE function_sql;
        END
        $migration$
        """
    )
    op.execute("ALTER TABLE public.test_personnel_deletion_requests DROP CONSTRAINT ck_tpdr_status")
    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_requests
        ADD CONSTRAINT ck_tpdr_status CHECK (status IN (
            'DRAFT', 'PENDING_HR_APPROVAL', 'APPROVED', 'REJECTED',
            'REAPPROVAL_REQUIRED', 'CANCELLED', 'EXPIRED'
        ))
        """
    )
