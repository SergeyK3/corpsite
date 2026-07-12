"""OO-IMP-004 — Document lifecycle CREATED → READY_FOR_SIGNATURE."""
from __future__ import annotations

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "z0a1b2c3d4e5"
branch_labels = None
depends_on = None

_PARTY_REFERENCE_TYPES = ("PERSON", "POSITION_ROLE", "ORG_UNIT")
_SIGNING_AUTHORITY_STATUSES = ("ACTIVE", "SUPERSEDED", "REVOKED")
_LIFECYCLE_AUDIT_ACTIONS = (
    "SIGNING_AUTHORITY_ASSIGNED",
    "SIGNING_AUTHORITY_SUPERSEDED",
    "SIGNATURE_READINESS_VALIDATED",
    "SIGNATURE_READINESS_FAILED",
    "DOCUMENT_READY_FOR_SIGNATURE",
    "READY_FOR_SIGNATURE_REPLAY",
    "DOCUMENT_RETURNED_TO_CREATED",
)
_OO_PERMISSIONS = (
    "OPERATIONAL_ORDERS_SIGNATURE_READINESS_READ",
    "OPERATIONAL_ORDERS_ASSIGN_SIGNING_AUTHORITY",
    "OPERATIONAL_ORDERS_MARK_READY_FOR_SIGNATURE",
    "OPERATIONAL_ORDERS_RETURN_FROM_SIGNATURE",
)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    party_types_sql = _in_list(_PARTY_REFERENCE_TYPES)
    authority_statuses_sql = _in_list(_SIGNING_AUTHORITY_STATUSES)
    lifecycle_actions_sql = _in_list(_LIFECYCLE_AUDIT_ACTIONS)

    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            ADD COLUMN IF NOT EXISTS ready_for_signature_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS ready_for_signature_by_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_signing_authority (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            document_id BIGINT NOT NULL
                REFERENCES public.operational_order_documents (id)
                ON DELETE CASCADE,
            document_version_id BIGINT NOT NULL
                REFERENCES public.operational_order_document_versions (id)
                ON DELETE CASCADE,
            authority_party_type TEXT NOT NULL,
            authority_party_reference TEXT NOT NULL,
            authority_display_name TEXT NULL,
            authority_position_id BIGINT NULL,
            authority_org_unit_id BIGINT NULL
                REFERENCES public.org_units (unit_id) ON DELETE SET NULL,
            authority_basis TEXT NULL,
            assigned_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            superseded_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            version INTEGER NOT NULL DEFAULT 1,
            CONSTRAINT chk_oo_signing_authority_party_type
                CHECK (authority_party_type IN ({party_types_sql})),
            CONSTRAINT chk_oo_signing_authority_status
                CHECK (status IN ({authority_statuses_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_signing_authority_document
            ON public.operational_order_signing_authority (document_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_signing_authority_version
            ON public.operational_order_signing_authority (document_version_id)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_oo_signing_authority_active_document
            ON public.operational_order_signing_authority (document_id)
            WHERE status = 'ACTIVE'
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_lifecycle_audit (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            document_id BIGINT NOT NULL
                REFERENCES public.operational_order_documents (id)
                ON DELETE CASCADE,
            document_version_id BIGINT NULL
                REFERENCES public.operational_order_document_versions (id)
                ON DELETE SET NULL,
            transition_from TEXT NULL,
            transition_to TEXT NULL,
            action TEXT NOT NULL,
            actor_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            actor_party_type TEXT NULL,
            actor_party_reference TEXT NULL,
            reason TEXT NULL,
            metadata_json JSONB NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            document_version_before INTEGER NULL,
            document_version_after INTEGER NULL,
            CONSTRAINT chk_oo_lifecycle_audit_action
                CHECK (action IN ({lifecycle_actions_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_lifecycle_audit_document
            ON public.operational_order_lifecycle_audit (document_id)
        """
    )

    for permission in _OO_PERMISSIONS:
        display_name = permission.replace("_", " ").title()
        op.execute(
            f"""
            INSERT INTO public.access_roles (
                code, name, description, access_level, level_rank, is_system
            )
            VALUES (
                '{permission}',
                '{display_name}',
                'OO-IMP-004 lifecycle permission ({permission})',
                'MANAGER', 20, TRUE
            )
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                access_level = EXCLUDED.access_level,
                level_rank = EXCLUDED.level_rank,
                is_system = EXCLUDED.is_system,
                is_active = TRUE,
                updated_at = now()
            """
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.operational_order_lifecycle_audit CASCADE")
    op.execute("DROP TABLE IF EXISTS public.operational_order_signing_authority CASCADE")
    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            DROP COLUMN IF EXISTS ready_for_signature_by_user_id,
            DROP COLUMN IF EXISTS ready_for_signature_at
        """
    )

    for permission in _OO_PERMISSIONS:
        op.execute(
            f"""
            DELETE FROM public.access_grants
            WHERE access_role_id IN (
                SELECT access_role_id FROM public.access_roles WHERE code = '{permission}'
            )
            """
        )
        op.execute(
            f"""
            DELETE FROM public.access_roles WHERE code = '{permission}'
            """
        )
