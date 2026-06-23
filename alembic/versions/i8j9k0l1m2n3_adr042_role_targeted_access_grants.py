"""ADR-042 — allow ROLE target_type on access_grants.

Revision ID: i8j9k0l1m2n3
Revises: h7i8j9k0l1m2
"""
from __future__ import annotations

from alembic import op

revision = "i8j9k0l1m2n3"
down_revision = "h7i8j9k0l1m2"
branch_labels = None
depends_on = None

_TARGET_TYPES = (
    "PERSON",
    "ASSIGNMENT",
    "POSITION",
    "ORG_UNIT",
    "EMPLOYEE",
    "USER",
    "ROLE",
)

_LEGACY_TARGET_TYPES = (
    "PERSON",
    "ASSIGNMENT",
    "POSITION",
    "ORG_UNIT",
    "EMPLOYEE",
    "USER",
)


def _target_types_sql(types: tuple[str, ...]) -> str:
    return ", ".join(f"'{t}'" for t in types)


def upgrade() -> None:
    target_types_sql = _target_types_sql(_TARGET_TYPES)
    op.execute(
        """
        ALTER TABLE public.access_grants
            DROP CONSTRAINT IF EXISTS chk_ag_target_type
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.access_grants
            ADD CONSTRAINT chk_ag_target_type
                CHECK (target_type IN ({target_types_sql}))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.access_grants
                WHERE target_type = 'ROLE'
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade i8j9k0l1m2n3: ROLE-targeted access_grants exist';
            END IF;
        END $$;
        """
    )
    legacy_sql = _target_types_sql(_LEGACY_TARGET_TYPES)
    op.execute(
        """
        ALTER TABLE public.access_grants
            DROP CONSTRAINT IF EXISTS chk_ag_target_type
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.access_grants
            ADD CONSTRAINT chk_ag_target_type
                CHECK (target_type IN ({legacy_sql}))
        """
    )
