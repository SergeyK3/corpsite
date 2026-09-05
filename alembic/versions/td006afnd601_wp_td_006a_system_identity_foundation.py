"""WP-TD-006A: test system identity deletion foundation (no execution API).

Revision ID: td006afnd601
Revises: td005exec501
"""
from __future__ import annotations

from alembic import op


revision = "td006afnd601"
down_revision = "td005exec501"
branch_labels = None
depends_on = None


_OWNER_MARKER = "WP-TD-006A:td006afnd601"
_SYSTEM_PURPOSE = "HISTORICAL_AUTHORSHIP"
_PERMISSIONS = {
    "TEST_SYSTEM_IDENTITY_DELETION_REQUEST": "Request test system identity deletion",
    "TEST_SYSTEM_IDENTITY_DELETION_APPROVE": "Approve test system identity deletion",
    "TEST_SYSTEM_IDENTITY_DELETION_EXECUTE": "Execute approved test system identity deletion",
    "TEST_SYSTEM_IDENTITY_DELETION_AUDIT_READ": "Read test system identity deletion audit",
}


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF (SELECT COUNT(*) FROM public.roles
                WHERE code='ADMIN') <> 1 THEN
                RAISE EXCEPTION 'WP_TD_006A_CANONICAL_ADMIN_ROLE_REQUIRED';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM public.users WHERE is_active=TRUE) THEN
                RAISE EXCEPTION 'WP_TD_006A_ACTIVE_GRANTOR_REQUIRED';
            END IF;
        END $$
        """
    )

    op.execute(
        """
        ALTER TABLE public.users
            ADD COLUMN is_system_identity BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN system_identity_purpose TEXT NULL,
            ADD CONSTRAINT ck_users_system_identity_purpose CHECK (
                (is_system_identity=FALSE AND system_identity_purpose IS NULL)
                OR (
                    is_system_identity=TRUE
                    AND system_identity_purpose='HISTORICAL_AUTHORSHIP'
                    AND employee_id IS NULL
                    AND unit_id IS NULL
                    AND is_active=FALSE
                    AND locked_at IS NOT NULL
                    AND locked_reason='policy'
                    AND login IS NULL
                    AND google_login IS NULL
                    AND password_hash IS NULL
                    AND phone IS NULL
                    AND telegram_id IS NULL
                    AND telegram_username IS NULL
                    AND telegram_bound_at IS NULL
                )
            )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_users_system_identity_purpose
        ON public.users(system_identity_purpose)
        WHERE is_system_identity=TRUE
        """
    )
    op.execute(
        f"""
        INSERT INTO public.users (
            full_name, google_login, phone, telegram_id, role_id, unit_id,
            is_active, telegram_username, telegram_bound_at, login,
            password_hash, employee_id, must_change_password, locked_at,
            locked_until, locked_reason, is_system_identity,
            system_identity_purpose
        )
        SELECT
            'System historical authorship', NULL, NULL, NULL, role_id, NULL,
            FALSE, NULL, NULL, NULL, NULL, NULL, FALSE,
            statement_timestamp(), NULL, 'policy', TRUE,
            '{_SYSTEM_PURPOSE}'
        FROM public.roles
        WHERE code='ADMIN'
          AND NOT EXISTS (
              SELECT 1 FROM public.users
              WHERE is_system_identity=TRUE
                AND system_identity_purpose='{_SYSTEM_PURPOSE}'
          )
        """
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            IF (SELECT COUNT(*) FROM public.users
                WHERE is_system_identity=TRUE
                  AND system_identity_purpose='{_SYSTEM_PURPOSE}'
                  AND employee_id IS NULL
                  AND unit_id IS NULL
                  AND is_active=FALSE
                  AND locked_at IS NOT NULL
                  AND locked_reason='policy'
                  AND login IS NULL
                  AND google_login IS NULL
                  AND password_hash IS NULL
                  AND phone IS NULL
                  AND telegram_id IS NULL
                  AND telegram_username IS NULL
                  AND telegram_bound_at IS NULL) <> 1 THEN
                RAISE EXCEPTION 'WP_TD_006A_HISTORICAL_IDENTITY_INVALID';
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.td006a_protect_system_identity() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP='TRUNCATE' THEN
                RAISE EXCEPTION 'WP_TD_006A_SYSTEM_IDENTITY_PROTECTED';
            END IF;
            IF TG_OP='DELETE' AND OLD.is_system_identity THEN
                RAISE EXCEPTION 'WP_TD_006A_SYSTEM_IDENTITY_PROTECTED';
            END IF;
            IF TG_OP='UPDATE' AND (
                OLD.is_system_identity
                OR NEW.is_system_identity IS DISTINCT FROM OLD.is_system_identity
                OR NEW.system_identity_purpose IS DISTINCT FROM OLD.system_identity_purpose
            ) THEN
                RAISE EXCEPTION 'WP_TD_006A_SYSTEM_IDENTITY_PROTECTED';
            END IF;
            IF TG_OP='INSERT' AND NEW.is_system_identity THEN
                RAISE EXCEPTION 'WP_TD_006A_SYSTEM_IDENTITY_MIGRATION_OWNED';
            END IF;
            RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_users_protect_system_identity
        BEFORE INSERT OR UPDATE OR DELETE ON public.users
        FOR EACH ROW EXECUTE FUNCTION public.td006a_protect_system_identity()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_users_protect_system_identity_truncate
        BEFORE TRUNCATE ON public.users
        FOR EACH STATEMENT EXECUTE FUNCTION public.td006a_protect_system_identity()
        """
    )

    op.execute(
        """
        CREATE TABLE public.test_system_identity_provenance (
            provenance_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            object_type TEXT NOT NULL,
            object_id BIGINT NOT NULL,
            user_id BIGINT GENERATED ALWAYS AS (
                CASE WHEN object_type='USER' THEN object_id ELSE NULL END
            ) STORED,
            role_id BIGINT GENERATED ALWAYS AS (
                CASE WHEN object_type='ROLE' THEN object_id ELSE NULL END
            ) STORED,
            source TEXT NOT NULL,
            artifact_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
            created_by_user_id BIGINT NOT NULL,
            CONSTRAINT ck_tsip_object_type CHECK (object_type IN ('USER','ROLE')),
            CONSTRAINT ck_tsip_object_id CHECK (object_id > 0),
            CONSTRAINT ck_tsip_typed_target CHECK (
                (object_type='USER' AND user_id=object_id AND role_id IS NULL)
                OR (object_type='ROLE' AND role_id=object_id AND user_id IS NULL)
            ),
            CONSTRAINT ck_tsip_source CHECK (
                length(btrim(source)) BETWEEN 1 AND 128
            ),
            CONSTRAINT ck_tsip_artifact_hash CHECK (
                artifact_hash ~ '^[0-9a-f]{64}$'
            ),
            CONSTRAINT fk_tsip_user FOREIGN KEY (user_id)
                REFERENCES public.users(user_id) ON DELETE RESTRICT,
            CONSTRAINT fk_tsip_role FOREIGN KEY (role_id)
                REFERENCES public.roles(role_id) ON DELETE RESTRICT,
            CONSTRAINT fk_tsip_created_by FOREIGN KEY (created_by_user_id)
                REFERENCES public.users(user_id) ON DELETE RESTRICT,
            CONSTRAINT uq_tsip_origin_confirmation UNIQUE (
                object_type, object_id, source, artifact_hash
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_tsip_target "
        "ON public.test_system_identity_provenance(object_type,object_id,created_at)"
    )
    op.execute(
        """
        CREATE FUNCTION public.td006a_system_provenance_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.object_type='USER' AND EXISTS (
                SELECT 1 FROM public.users
                WHERE user_id=NEW.object_id AND is_system_identity=TRUE
            ) THEN
                RAISE EXCEPTION 'WP_TD_006A_SYSTEM_IDENTITY_NOT_A_DELETION_CANDIDATE';
            END IF;
            NEW.created_at := statement_timestamp();
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_tsip_insert_guard
        BEFORE INSERT ON public.test_system_identity_provenance
        FOR EACH ROW EXECUTE FUNCTION public.td006a_system_provenance_guard()
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.td006a_reject_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'WP_TD_006A_APPEND_ONLY';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_tsip_append_only
        BEFORE UPDATE OR DELETE ON public.test_system_identity_provenance
        FOR EACH ROW EXECUTE FUNCTION public.td006a_reject_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_tsip_truncate_guard
        BEFORE TRUNCATE ON public.test_system_identity_provenance
        FOR EACH STATEMENT EXECUTE FUNCTION public.td006a_reject_mutation()
        """
    )

    for code, name in _PERMISSIONS.items():
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM public.access_roles WHERE code='{code}') THEN
                    RAISE EXCEPTION 'WP_TD_006A_PERMISSION_CODE_CONFLICT:{code}';
                END IF;
                INSERT INTO public.access_roles (
                    code,name,description,access_level,level_rank,is_system
                ) VALUES (
                    '{code}','{name}','{_OWNER_MARKER}','MANAGER',20,TRUE
                );
            END $$
            """
        )
        op.execute(
            f"""
            INSERT INTO public.access_grants (
                access_role_id,target_type,target_id,granted_by_user_id,reason
            )
            SELECT ar.access_role_id,'ROLE',admin_role.role_id,grantor.user_id,
                   '{_OWNER_MARKER}:{code}:ADMIN'
            FROM public.access_roles ar
            JOIN public.roles admin_role ON admin_role.code='ADMIN'
            CROSS JOIN LATERAL (
                SELECT user_id FROM public.users
                WHERE is_active=TRUE
                ORDER BY CASE WHEN lower(login)='admin' THEN 0 ELSE 1 END,user_id
                LIMIT 1
            ) grantor
            WHERE ar.code='{code}'
            """
        )


def downgrade() -> None:
    codes = ", ".join(f"'{code}'" for code in sorted(_PERMISSIONS))
    reasons = ", ".join(
        f"'{_OWNER_MARKER}:{code}:ADMIN'" for code in sorted(_PERMISSIONS)
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.test_system_identity_provenance) THEN
                RAISE EXCEPTION 'WP_TD_006A_PROVENANCE_PREVENTS_DOWNGRADE';
            END IF;
            IF (SELECT COUNT(*) FROM public.access_roles
                WHERE code IN ({codes}) AND description='{_OWNER_MARKER}')
                <> {len(_PERMISSIONS)} THEN
                RAISE EXCEPTION 'WP_TD_006A_RBAC_OWNERSHIP_MISMATCH';
            END IF;
            IF (SELECT COUNT(*) FROM public.access_grants grant_def
                JOIN public.access_roles access_role
                  ON access_role.access_role_id=grant_def.access_role_id
                WHERE access_role.code IN ({codes})
                  AND access_role.description='{_OWNER_MARKER}')
                <> {len(_PERMISSIONS)} THEN
                RAISE EXCEPTION 'WP_TD_006A_RBAC_GRANT_COUNT_MISMATCH';
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.access_grants grant_def
                JOIN public.access_roles access_role
                  ON access_role.access_role_id=grant_def.access_role_id
                LEFT JOIN public.roles target_role
                  ON grant_def.target_type='ROLE'
                 AND target_role.role_id=grant_def.target_id
                WHERE access_role.code IN ({codes})
                  AND (
                      access_role.description IS DISTINCT FROM '{_OWNER_MARKER}'
                      OR target_role.code IS DISTINCT FROM 'ADMIN'
                      OR grant_def.reason NOT IN ({reasons})
                      OR grant_def.active_flag IS DISTINCT FROM TRUE
                  )
            ) THEN
                RAISE EXCEPTION 'WP_TD_006A_EXTERNAL_GRANTS_PRESENT';
            END IF;
        END $$
        """
    )
    op.execute(
        f"""
        DELETE FROM public.access_grants grant_def
        USING public.access_roles access_role
        WHERE grant_def.access_role_id=access_role.access_role_id
          AND access_role.code IN ({codes})
          AND access_role.description='{_OWNER_MARKER}'
          AND grant_def.reason IN ({reasons})
        """
    )
    op.execute(
        f"DELETE FROM public.access_roles "
        f"WHERE code IN ({codes}) AND description='{_OWNER_MARKER}'"
    )

    op.execute(
        "DROP TRIGGER trg_tsip_truncate_guard "
        "ON public.test_system_identity_provenance"
    )
    op.execute(
        "DROP TRIGGER trg_tsip_append_only "
        "ON public.test_system_identity_provenance"
    )
    op.execute(
        "DROP TRIGGER trg_tsip_insert_guard "
        "ON public.test_system_identity_provenance"
    )
    op.execute("DROP FUNCTION public.td006a_reject_mutation()")
    op.execute("DROP FUNCTION public.td006a_system_provenance_guard()")
    op.execute("DROP TABLE public.test_system_identity_provenance")

    op.execute(
        f"""
        DO $$
        DECLARE
            protected_user_id BIGINT;
            reference RECORD;
            has_reference BOOLEAN;
        BEGIN
            SELECT user_id INTO STRICT protected_user_id
            FROM public.users
            WHERE is_system_identity=TRUE
              AND system_identity_purpose='{_SYSTEM_PURPOSE}';

            FOR reference IN
                SELECT child_ns.nspname AS schema_name,
                       child.relname AS table_name,
                       child_attr.attname AS column_name
                FROM pg_constraint constraint_def
                JOIN pg_class parent ON parent.oid=constraint_def.confrelid
                JOIN pg_namespace parent_ns ON parent_ns.oid=parent.relnamespace
                JOIN pg_class child ON child.oid=constraint_def.conrelid
                JOIN pg_namespace child_ns ON child_ns.oid=child.relnamespace
                JOIN LATERAL unnest(constraint_def.conkey)
                     WITH ORDINALITY child_key(attnum,ordinality) ON TRUE
                JOIN pg_attribute child_attr
                  ON child_attr.attrelid=child.oid
                 AND child_attr.attnum=child_key.attnum
                WHERE constraint_def.contype='f'
                  AND parent_ns.nspname='public'
                  AND parent.relname='users'
            LOOP
                EXECUTE format(
                    'SELECT EXISTS (SELECT 1 FROM %I.%I WHERE %I=$1)',
                    reference.schema_name, reference.table_name,
                    reference.column_name
                ) INTO has_reference USING protected_user_id;
                IF has_reference THEN
                    RAISE EXCEPTION
                        'WP_TD_006A_TECHNICAL_USER_REFERENCED:%.%',
                        reference.table_name, reference.column_name;
                END IF;
            END LOOP;

            IF EXISTS (
                SELECT 1 FROM public.access_grants
                WHERE target_type='USER' AND target_id=protected_user_id
            ) THEN
                RAISE EXCEPTION
                    'WP_TD_006A_TECHNICAL_USER_LOGICALLY_REFERENCED:access_grants';
            END IF;

            -- These legacy/control-plane author columns intentionally have no
            -- database FK. They remain historical references and therefore
            -- block downgrade exactly like a physical FK.
            FOR reference IN
                SELECT * FROM (VALUES
                    ('contact_access', 'changed_by_user_id'),
                    ('hr_baseline_deletion_log', 'published_by'),
                    ('hr_import_diff_removals', 'decided_by'),
                    ('regular_tasks_stg', 'created_by_user_id'),
                    ('test_personnel_deletion_decisions', 'actor_user_id'),
                    ('test_personnel_deletion_execution_attempts', 'executor_user_id'),
                    ('test_personnel_deletion_history', 'actor_user_id'),
                    ('test_personnel_deletion_requests', 'initiated_by_user_id'),
                    ('test_personnel_provenance', 'created_by_user_id')
                ) AS known_logical(table_name, column_name)
            LOOP
                IF to_regclass(format('public.%I', reference.table_name)) IS NOT NULL
                   AND EXISTS (
                       SELECT 1 FROM information_schema.columns
                       WHERE table_schema='public'
                         AND table_name=reference.table_name
                         AND column_name=reference.column_name
                   ) THEN
                    EXECUTE format(
                        'SELECT EXISTS (SELECT 1 FROM public.%I WHERE %I=$1)',
                        reference.table_name, reference.column_name
                    ) INTO has_reference USING protected_user_id;
                    IF has_reference THEN
                        RAISE EXCEPTION
                            'WP_TD_006A_TECHNICAL_USER_LOGICALLY_REFERENCED:%.%',
                            reference.table_name, reference.column_name;
                    END IF;
                END IF;
            END LOOP;
        END $$
        """
    )
    op.execute(
        "DROP TRIGGER trg_users_protect_system_identity_truncate ON public.users"
    )
    op.execute("DROP TRIGGER trg_users_protect_system_identity ON public.users")
    op.execute("DROP FUNCTION public.td006a_protect_system_identity()")
    op.execute(
        f"""
        DO $$
        DECLARE deleted_count INTEGER;
        BEGIN
            DELETE FROM public.users
            WHERE is_system_identity=TRUE
              AND system_identity_purpose='{_SYSTEM_PURPOSE}'
              AND employee_id IS NULL
              AND is_active=FALSE
              AND login IS NULL
              AND google_login IS NULL
              AND password_hash IS NULL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            IF deleted_count <> 1 THEN
                RAISE EXCEPTION 'WP_TD_006A_TECHNICAL_USER_OWNERSHIP_MISMATCH';
            END IF;
        END $$
        """
    )
    op.execute("DROP INDEX public.uq_users_system_identity_purpose")
    op.execute(
        "ALTER TABLE public.users DROP CONSTRAINT ck_users_system_identity_purpose"
    )
    op.execute(
        "ALTER TABLE public.users "
        "DROP COLUMN system_identity_purpose, DROP COLUMN is_system_identity"
    )
