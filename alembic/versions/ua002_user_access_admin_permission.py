"""WP-ACCESS-002: seed the explicit user-access administration permission.

Revision ID: ua002accessadmin
Revises: adm001canonicalroles

This continues the canonical administrative-role head.  The independent data
exchange head remains deliberately unmerged.  The migration creates only the
permission catalogue row: it grants USER_ACCESS_ADMIN to no role and no user.
"""
from alembic import op


revision = "ua002accessadmin"
down_revision = "adm001canonicalroles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO public.access_roles (
            code, name, description, access_level, level_rank, is_system
        ) VALUES (
            'USER_ACCESS_ADMIN',
            'User Access Administrator',
            'Read and administer employee account access only when explicitly granted to a user.',
            'MANAGER',
            20,
            TRUE
        )
        ON CONFLICT (code) DO UPDATE
        SET is_active = TRUE, updated_at = now()
    """)


def downgrade() -> None:
    # A downgrade must not silently revoke a grant created after the migration.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.access_grants g
                JOIN public.access_roles r ON r.access_role_id = g.access_role_id
                WHERE r.code = 'USER_ACCESS_ADMIN'
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade ua002accessadmin while USER_ACCESS_ADMIN grants exist';
            END IF;
        END $$;
    """)
    op.execute("DELETE FROM public.access_roles WHERE code = 'USER_ACCESS_ADMIN'")
