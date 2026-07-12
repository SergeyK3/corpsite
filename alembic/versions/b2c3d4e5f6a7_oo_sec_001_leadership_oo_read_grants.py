"""OO-SEC-001 — Leadership Workspace Read Policy: ROLE grants for OPERATIONAL_ORDERS_INTAKE_READ.

Mirrors ADR-045 / WP-PO-LC-DEL-004 pattern: access_grants.target_type = ROLE.
Only roles in the approved allowlist at migration time receive grants.

Keep _APPROVED_ROLE_CODES in sync with
app.security.platform_role_classification.LEADERSHIP_PLATFORM_ROLE_CODES.
"""
from __future__ import annotations

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

_PERMISSION_CODE = "OPERATIONAL_ORDERS_INTAKE_READ"
_GRANT_REASON = "OO-SEC-001: approved leadership workspace read policy"

# Approved allowlist — explicit policy review required for each code.
_APPROVED_ROLE_CODES: tuple[str, ...] = (
    "DIRECTOR",
    "DEP_MED",
    "DEP_OUTPATIENT_AUDIT",
    "DEP_ADMIN",
    "DEP_STRATEGY",
    "STAT_HEAD",
    "STAT_HEAD_DEPUTY",
    "QM_HEAD",
    "HR_HEAD",
    "ACC_HEAD",
    "ECON_HEAD",
)


def _sql_in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{code}'" for code in values)


def upgrade() -> None:
    codes_sql = _sql_in_list(_APPROVED_ROLE_CODES)
    reason = _GRANT_REASON.replace("'", "''")
    op.execute(
        f"""
        INSERT INTO public.access_grants (
            access_role_id,
            target_type,
            target_id,
            granted_by_user_id,
            reason
        )
        SELECT
            ar.access_role_id,
            'ROLE',
            r.role_id,
            COALESCE(
                (
                    SELECT u.user_id
                    FROM public.users u
                    WHERE lower(u.login) = 'admin'
                      AND u.is_active = TRUE
                    ORDER BY u.user_id
                    LIMIT 1
                ),
                1
            ),
            '{reason}'
        FROM public.access_roles ar
        CROSS JOIN public.roles r
        WHERE ar.code = '{_PERMISSION_CODE}'
          AND ar.is_active = TRUE
          AND r.code IN ({codes_sql})
          AND NOT EXISTS (
              SELECT 1
              FROM public.access_grants g
              WHERE g.active_flag = TRUE
                AND g.access_role_id = ar.access_role_id
                AND g.target_type = 'ROLE'
                AND g.target_id = r.role_id
          )
        """
    )


def downgrade() -> None:
    codes_sql = _sql_in_list(_APPROVED_ROLE_CODES)
    reason = _GRANT_REASON.replace("'", "''")
    op.execute(
        f"""
        DELETE FROM public.access_grants g
        USING public.access_roles ar, public.roles r
        WHERE g.access_role_id = ar.access_role_id
          AND g.target_type = 'ROLE'
          AND g.target_id = r.role_id
          AND ar.code = '{_PERMISSION_CODE}'
          AND r.code IN ({codes_sql})
          AND g.reason = '{reason}'
        """
    )
