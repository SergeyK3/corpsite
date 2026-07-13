"""OO-IMP-005C — Signing command (READY_FOR_SIGNATURE → SIGNED)."""
from __future__ import annotations

from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

_LIFECYCLE_AUDIT_ACTIONS = (
    "SIGNING_AUTHORITY_ASSIGNED",
    "SIGNING_AUTHORITY_SUPERSEDED",
    "SIGNATURE_READINESS_VALIDATED",
    "SIGNATURE_READINESS_FAILED",
    "DOCUMENT_READY_FOR_SIGNATURE",
    "READY_FOR_SIGNATURE_REPLAY",
    "DOCUMENT_RETURNED_TO_CREATED",
    "DOCUMENT_SIGNED",
)
_OO_PERMISSIONS = ("OPERATIONAL_ORDERS_SIGN",)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    lifecycle_actions_sql = _in_list(_LIFECYCLE_AUDIT_ACTIONS)

    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            ADD COLUMN IF NOT EXISTS signing_authority_id BIGINT NULL
                REFERENCES public.operational_order_signing_authority (id)
                ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS signatory_display_name TEXT NULL,
            ADD COLUMN IF NOT EXISTS signatory_party_reference TEXT NULL,
            ADD COLUMN IF NOT EXISTS signatory_position TEXT NULL
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.operational_order_signing_attestations (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            document_id BIGINT NOT NULL
                REFERENCES public.operational_order_documents (id)
                ON DELETE CASCADE,
            signing_authority_id BIGINT NOT NULL
                REFERENCES public.operational_order_signing_authority (id)
                ON DELETE RESTRICT,
            document_version_id BIGINT NOT NULL
                REFERENCES public.operational_order_document_versions (id)
                ON DELETE RESTRICT,
            actor_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            actor_employee_id BIGINT NULL
                REFERENCES public.employees (employee_id) ON DELETE SET NULL,
            assigned_authority_party_type TEXT NOT NULL,
            assigned_authority_party_reference TEXT NOT NULL,
            assigned_authority_display_name TEXT NULL,
            assigned_authority_position_id BIGINT NULL,
            assigned_authority_org_unit_id BIGINT NULL
                REFERENCES public.org_units (unit_id) ON DELETE SET NULL,
            assigned_authority_basis TEXT NULL,
            signatory_position_name TEXT NULL,
            privileged_override BOOLEAN NOT NULL DEFAULT FALSE,
            override_reason TEXT NULL,
            signed_at TIMESTAMPTZ NOT NULL,
            snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_oo_signing_attestations_document UNIQUE (document_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_signing_attestations_authority
            ON public.operational_order_signing_attestations (signing_authority_id)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.operational_order_lifecycle_command_idempotency (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            idempotency_key TEXT NOT NULL,
            command_type TEXT NOT NULL,
            document_id BIGINT NOT NULL
                REFERENCES public.operational_order_documents (id)
                ON DELETE CASCADE,
            actor_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            request_payload_hash TEXT NOT NULL,
            attestation_id BIGINT NULL
                REFERENCES public.operational_order_signing_attestations (id)
                ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_oo_lifecycle_command_idempotency_key UNIQUE (idempotency_key)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_lifecycle_command_idempotency_document
            ON public.operational_order_lifecycle_command_idempotency (document_id, command_type)
        """
    )

    op.execute(
        """
        ALTER TABLE public.operational_order_lifecycle_audit
            DROP CONSTRAINT IF EXISTS chk_oo_lifecycle_audit_action
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.operational_order_lifecycle_audit
            ADD CONSTRAINT chk_oo_lifecycle_audit_action
                CHECK (action IN ({lifecycle_actions_sql}))
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
                'OO-IMP-005C signing command permission ({permission})',
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

    previous_actions_sql = _in_list(
        (
            "SIGNING_AUTHORITY_ASSIGNED",
            "SIGNING_AUTHORITY_SUPERSEDED",
            "SIGNATURE_READINESS_VALIDATED",
            "SIGNATURE_READINESS_FAILED",
            "DOCUMENT_READY_FOR_SIGNATURE",
            "READY_FOR_SIGNATURE_REPLAY",
            "DOCUMENT_RETURNED_TO_CREATED",
        )
    )
    op.execute(
        """
        DELETE FROM public.operational_order_lifecycle_audit
        WHERE action = 'DOCUMENT_SIGNED'
        """
    )
    op.execute(
        """
        ALTER TABLE public.operational_order_lifecycle_audit
            DROP CONSTRAINT IF EXISTS chk_oo_lifecycle_audit_action
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.operational_order_lifecycle_audit
            ADD CONSTRAINT chk_oo_lifecycle_audit_action
                CHECK (action IN ({previous_actions_sql}))
        """
    )

    op.execute("DROP TABLE IF EXISTS public.operational_order_lifecycle_command_idempotency CASCADE")
    op.execute("DROP TABLE IF EXISTS public.operational_order_signing_attestations CASCADE")

    op.execute(
        """
        ALTER TABLE public.operational_order_documents
            DROP COLUMN IF EXISTS signatory_position,
            DROP COLUMN IF EXISTS signatory_party_reference,
            DROP COLUMN IF EXISTS signatory_display_name,
            DROP COLUMN IF EXISTS signing_authority_id
        """
    )
