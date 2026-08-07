"""Grant HR_HEAD the separate Incoming Information registration permission."""
from __future__ import annotations

from alembic import op

revision = "i6j7k8l9m0n1"
down_revision = "h5c6d7e8f9a0"
branch_labels = None
depends_on = None

_PERMISSION_CODE = "INCOMING_INFO_REGISTER"
_ROLE_CODE = "HR_HEAD"
_GRANT_REASON = "i6j7k8l9m0n1: HR_HEAD Incoming Information registration grant"


def upgrade() -> None:
    op.execute(
        f"""
        DO $migration$
        DECLARE
            v_role_id BIGINT;
            v_role_count INTEGER;
            v_access_role_id BIGINT;
            v_permission_count INTEGER;
            v_permission_active BOOLEAN;
            v_granted_by_user_id BIGINT;
        BEGIN
            SELECT COUNT(*), MIN(role_id)
            INTO v_role_count, v_role_id
            FROM public.roles
            WHERE code = '{_ROLE_CODE}';

            IF v_role_count <> 1 THEN
                RAISE EXCEPTION
                    'i6j7k8l9m0n1 requires exactly one role with code %, found %',
                    '{_ROLE_CODE}', v_role_count;
            END IF;

            SELECT COUNT(*), MIN(access_role_id), BOOL_AND(is_active)
            INTO v_permission_count, v_access_role_id, v_permission_active
            FROM public.access_roles
            WHERE code = '{_PERMISSION_CODE}';

            IF v_permission_count <> 1 THEN
                RAISE EXCEPTION
                    'i6j7k8l9m0n1 requires exactly one permission with code %, found %',
                    '{_PERMISSION_CODE}', v_permission_count;
            END IF;

            IF v_permission_active IS DISTINCT FROM TRUE THEN
                RAISE EXCEPTION
                    'i6j7k8l9m0n1 requires active permission %',
                    '{_PERMISSION_CODE}';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM public.access_grants g
                WHERE g.access_role_id = v_access_role_id
                  AND g.target_type = 'ROLE'
                  AND g.target_id = v_role_id
                  AND g.active_flag = TRUE
                  AND g.starts_at <= statement_timestamp()
                  AND (g.ends_at IS NULL OR g.ends_at > statement_timestamp())
            ) THEN
                RETURN;
            END IF;

            IF EXISTS (
                SELECT 1
                FROM public.access_grants g
                WHERE g.access_role_id = v_access_role_id
                  AND g.target_type = 'ROLE'
                  AND g.target_id = v_role_id
                  AND g.active_flag = TRUE
            ) THEN
                RAISE EXCEPTION
                    'i6j7k8l9m0n1 found a flagged-active but non-effective grant for role %',
                    v_role_id;
            END IF;

            SELECT u.user_id
            INTO v_granted_by_user_id
            FROM public.users u
            WHERE u.is_active = TRUE
            ORDER BY CASE WHEN lower(u.login) = 'admin' THEN 0 ELSE 1 END, u.user_id
            LIMIT 1;

            IF v_granted_by_user_id IS NULL THEN
                RAISE EXCEPTION
                    'i6j7k8l9m0n1 requires an active user for granted_by_user_id';
            END IF;

            INSERT INTO public.access_grants (
                access_role_id,
                target_type,
                target_id,
                granted_by_user_id,
                reason
            )
            VALUES (
                v_access_role_id,
                'ROLE',
                v_role_id,
                v_granted_by_user_id,
                '{_GRANT_REASON}'
            );
        END
        $migration$;
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM public.access_grants
        WHERE target_type = 'ROLE'
          AND reason = '{_GRANT_REASON}'
        """
    )
