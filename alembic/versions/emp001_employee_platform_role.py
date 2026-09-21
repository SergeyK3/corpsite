"""Add the neutral EMPLOYEE Platform Role.

Revision ID: emp001employee
Revises: aec001activecard
"""
from alembic import op


revision = "emp001employee"
down_revision = "aec001activecard"
branch_labels = None
depends_on = None


ROLE_CODE = "EMPLOYEE"
ROLE_NAME = "Сотрудник"


def upgrade() -> None:
    # This belongs to the primary personnel chain, not the independent Data
    # Exchange branch.  It intentionally creates no access_grants row.
    op.execute(
        """
        ALTER TABLE public.roles
            ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE
        """
    )
    op.execute(
        """
        INSERT INTO public.roles (code, name, is_active)
        VALUES ('EMPLOYEE', 'Сотрудник', TRUE)
        ON CONFLICT (code) DO UPDATE
            SET name = EXCLUDED.name,
                is_active = TRUE
        """
    )
    # A pre-existing same-code role carrying grants would not be neutral; fail
    # closed instead of silently revoking or inheriting privileged access.
    op.execute(
        """
        DO $$
        DECLARE employee_role_id BIGINT;
        BEGIN
            SELECT role_id INTO employee_role_id
            FROM public.roles
            WHERE code = 'EMPLOYEE';
            IF EXISTS (
                SELECT 1
                FROM public.access_grants
                WHERE target_type = 'ROLE'
                  AND target_id = employee_role_id
                  AND active_flag = TRUE
                  AND revoked_at IS NULL
            ) THEN
                RAISE EXCEPTION 'EMPLOYEE Platform Role must not have active access grants';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE employee_role_id BIGINT;
        BEGIN
            SELECT role_id INTO employee_role_id
            FROM public.roles
            WHERE code = 'EMPLOYEE';
            IF employee_role_id IS NULL THEN
                RETURN;
            END IF;
            IF EXISTS (SELECT 1 FROM public.users WHERE role_id = employee_role_id) THEN
                RAISE EXCEPTION 'Cannot remove EMPLOYEE role while users reference it';
            END IF;
            IF EXISTS (SELECT 1 FROM public.access_grants WHERE target_type = 'ROLE' AND target_id = employee_role_id) THEN
                RAISE EXCEPTION 'Cannot remove EMPLOYEE role while grants reference it';
            END IF;
            DELETE FROM public.roles WHERE role_id = employee_role_id;
        END $$;
        """
    )
