"""WP-TD-005 stage 4: execute permission gate and append-only audit contract.

Revision ID: td005audit401
Revises: td005fp3v101
"""
from __future__ import annotations

from alembic import op


revision = "td005audit401"
down_revision = "td005fp3v101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The permission was reserved by WP-TD-002A.  Stage 4 fails closed unless
    # that exact server-owned permission and its ADMIN-only default grant are
    # intact; it never grants execution to HR_HEAD.
    op.execute(
        """
        DO $$
        BEGIN
            IF (SELECT COUNT(*) FROM public.access_roles
                WHERE code='TEST_PERSONNEL_DELETION_EXECUTE'
                  AND description='WP-TD-002A:y8z9a0b1c2d3') <> 1 THEN
                RAISE EXCEPTION 'WP_TD_005_EXECUTE_PERMISSION_OWNERSHIP_MISMATCH';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM public.access_grants grant_def
                JOIN public.access_roles access_role
                  ON access_role.access_role_id=grant_def.access_role_id
                JOIN public.roles target_role
                  ON grant_def.target_type='ROLE' AND target_role.role_id=grant_def.target_id
                WHERE access_role.code='TEST_PERSONNEL_DELETION_EXECUTE'
                  AND target_role.code='ADMIN' AND grant_def.active_flag=TRUE
            ) THEN
                RAISE EXCEPTION 'WP_TD_005_ADMIN_EXECUTE_GRANT_REQUIRED';
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.access_grants grant_def
                JOIN public.access_roles access_role
                  ON access_role.access_role_id=grant_def.access_role_id
                JOIN public.roles target_role
                  ON grant_def.target_type='ROLE' AND target_role.role_id=grant_def.target_id
                WHERE access_role.code='TEST_PERSONNEL_DELETION_EXECUTE'
                  AND target_role.code='HR_HEAD' AND grant_def.active_flag=TRUE
            ) THEN
                RAISE EXCEPTION 'WP_TD_005_HR_HEAD_EXECUTE_GRANT_FORBIDDEN';
            END IF;
        END $$
        """
    )

    op.execute(
        "ALTER TABLE public.test_personnel_deletion_history "
        "DROP CONSTRAINT ck_tpdh_action"
    )
    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_history
        ADD CONSTRAINT ck_tpdh_action CHECK (action IN (
            'CREATE', 'SUBMIT', 'APPROVE', 'REJECT', 'CANCEL', 'EXPIRE',
            'RECHECK_FAILED', 'EXECUTE'
        ))
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_tpdh_execute_idempotency
        ON public.test_personnel_deletion_history (idempotency_key)
        WHERE action='EXECUTE'
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.td005_execute_projection_valid(
            projection JSONB,
            audit_request_id UUID,
            audit_executor_id BIGINT,
            audit_idempotency_key TEXT,
            audit_occurred_at TIMESTAMPTZ,
            audit_result_code TEXT
        ) RETURNS BOOLEAN
        LANGUAGE plpgsql
        IMMUTABLE
        STRICT
        AS $function$
        DECLARE
            item RECORD;
            key_count INTEGER := 0;
            allowed_keys CONSTANT TEXT[] := ARRAY[
                'request_id', 'executor_user_id', 'manifest_version',
                'fingerprint_version', 'target_set_hash',
                'relationship_fingerprint', 'policy_version', 'catalog_version',
                'catalog_fingerprint', 'table_counts', 'before_hash', 'after_hash',
                'idempotency_key', 'timestamp', 'result', 'error_code'
            ];
        BEGIN
            IF jsonb_typeof(projection) <> 'object'
               OR public.td002_jsonb_has_forbidden_key(projection) THEN
                RETURN FALSE;
            END IF;
            FOR item IN SELECT key, value FROM jsonb_each(projection)
            LOOP
                key_count := key_count + 1;
                IF NOT (item.key = ANY(allowed_keys)) THEN
                    RETURN FALSE;
                END IF;
            END LOOP;
            IF key_count <> cardinality(allowed_keys)
               OR NOT (projection ?& allowed_keys) THEN
                RETURN FALSE;
            END IF;
            IF projection->>'request_id' <> audit_request_id::text
               OR (projection->>'executor_user_id')::bigint <> audit_executor_id
               OR projection->>'idempotency_key' <> audit_idempotency_key
               OR projection->>'idempotency_key' !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
               OR (projection->>'timestamp')::timestamptz <> audit_occurred_at
               OR projection->>'result' <> audit_result_code
               OR (projection->>'manifest_version')::integer < 2
               OR projection->>'fingerprint_version' !~ '^WP-TD-RELATIONSHIP/v[0-9]+$'
               OR projection->>'target_set_hash' !~ '^[0-9a-f]{64}$'
               OR projection->>'relationship_fingerprint' !~ '^[0-9a-f]{64}$'
               OR projection->>'catalog_fingerprint' !~ '^[0-9a-f]{64}$'
               OR projection->>'before_hash' !~ '^[0-9a-f]{64}$'
               OR projection->>'after_hash' !~ '^[0-9a-f]{64}$'
               OR projection->>'policy_version' !~ '^WP-TD-[A-Z0-9-]+/v[0-9]+$'
               OR projection->>'catalog_version' !~ '^WP-TD-CATALOG/v[0-9]+$'
               OR projection->>'result' !~ '^TD_[A-Z0-9_]{1,124}$'
               OR (
                    projection->'error_code' <> 'null'::jsonb
                    AND projection->>'error_code' !~ '^TD_[A-Z0-9_]{1,124}$'
               )
               OR jsonb_typeof(projection->'table_counts') <> 'object' THEN
                RETURN FALSE;
            END IF;
            FOR item IN SELECT key, value FROM jsonb_each(projection->'table_counts')
            LOOP
                IF item.key !~ '^[a-z][a-z0-9_]{0,62}$'
                   OR jsonb_typeof(item.value) <> 'number'
                   OR (item.value #>> '{}') !~ '^(0|[1-9][0-9]*)$' THEN
                    RETURN FALSE;
                END IF;
            END LOOP;
            RETURN TRUE;
        EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range THEN
            RETURN FALSE;
        END
        $function$
        """
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
        CREATE FUNCTION public.td005_execute_audit_guard() RETURNS trigger
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
    op.execute(
        """
        CREATE TRIGGER trg_test_personnel_deletion_history_execute_guard
        BEFORE INSERT ON public.test_personnel_deletion_history
        FOR EACH ROW EXECUTE FUNCTION public.td005_execute_audit_guard()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_test_personnel_deletion_history_truncate_guard
        BEFORE TRUNCATE ON public.test_personnel_deletion_history
        FOR EACH STATEMENT EXECUTE FUNCTION public.td002_reject_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.test_personnel_deletion_history
                WHERE action='EXECUTE'
            ) THEN
                RAISE EXCEPTION 'WP_TD_005_EXECUTE_AUDIT_PREVENTS_DOWNGRADE';
            END IF;
        END $$
        """
    )
    op.execute(
        "DROP TRIGGER trg_test_personnel_deletion_history_truncate_guard "
        "ON public.test_personnel_deletion_history"
    )
    op.execute(
        "DROP TRIGGER trg_test_personnel_deletion_history_execute_guard "
        "ON public.test_personnel_deletion_history"
    )
    op.execute("DROP FUNCTION public.td005_execute_audit_guard()")
    op.execute("DROP INDEX public.uq_tpdh_execute_idempotency")
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_history "
        "DROP CONSTRAINT ck_tpdh_execute_contract"
    )
    op.execute("DROP FUNCTION public.td005_execute_projection_valid(JSONB,UUID,BIGINT,TEXT,TIMESTAMPTZ,TEXT)")
    op.execute(
        "ALTER TABLE public.test_personnel_deletion_history "
        "DROP CONSTRAINT ck_tpdh_action"
    )
    op.execute(
        """
        ALTER TABLE public.test_personnel_deletion_history
        ADD CONSTRAINT ck_tpdh_action CHECK (action IN (
            'CREATE', 'SUBMIT', 'APPROVE', 'REJECT', 'CANCEL', 'EXPIRE',
            'RECHECK_FAILED'
        ))
        """
    )
