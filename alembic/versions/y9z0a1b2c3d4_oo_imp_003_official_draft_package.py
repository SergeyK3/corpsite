"""OO-IMP-003 — Official draft package and document aggregate creation."""
from __future__ import annotations

from alembic import op

revision = "y9z0a1b2c3d4"
down_revision = "x8y9z0a1b2c3"
branch_labels = None
depends_on = None

_PROVENANCE_ACTIONS = (
    "SUBMISSION",
    "ACCEPTANCE",
    "EFFECTIVE_EDIT",
    "BLOCK_ADD",
    "TRANSLATION",
    "PROMOTED_FROM_WORKSPACE",
    "SNAPSHOT_CREATED",
    "DOCUMENT_VERSION_CREATED",
)
_DOCUMENT_STATUSES = (
    "CREATED",
    "READY_FOR_SIGNATURE",
    "SIGNED",
    "REGISTERED",
    "VOIDED",
)
_PROMOTION_STATUSES = ("STARTED", "COMPLETED", "FAILED")
_PROMOTION_AUDIT_ACTIONS = (
    "PROMOTION_STARTED",
    "PROMOTION_COMPLETED",
    "PROMOTION_FAILED",
    "DOCUMENT_CREATED",
    "VERSION_CREATED",
    "LOCALIZATION_SNAPSHOTTED",
)
_BLOCK_TYPES = (
    "TITLE",
    "PREAMBLE",
    "BODY",
    "ORDER_ITEM",
    "CONTROL",
    "ATTACHMENT_REFERENCE",
    "SIGNATURE_NOTE",
    "OTHER",
)
_LOCALES = ("ru", "kk")
_OO_PERMISSIONS = ("OPERATIONAL_ORDERS_PROMOTE",)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    provenance_actions_sql = _in_list(_PROVENANCE_ACTIONS)
    document_statuses_sql = _in_list(_DOCUMENT_STATUSES)
    promotion_statuses_sql = _in_list(_PROMOTION_STATUSES)
    promotion_audit_actions_sql = _in_list(_PROMOTION_AUDIT_ACTIONS)
    block_types_sql = _in_list(_BLOCK_TYPES)
    locales_sql = _in_list(_LOCALES)

    op.execute(
        """
        ALTER TABLE public.operational_order_text_provenance
            DROP CONSTRAINT IF EXISTS chk_oo_text_provenance_action
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.operational_order_text_provenance
            ADD CONSTRAINT chk_oo_text_provenance_action
                CHECK (action IN ({provenance_actions_sql}))
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_promotions (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            workspace_id BIGINT NOT NULL
                REFERENCES public.operational_order_draft_workspaces (workspace_id)
                ON DELETE RESTRICT,
            status TEXT NOT NULL DEFAULT 'STARTED',
            workspace_version INTEGER NOT NULL,
            workspace_fingerprint TEXT NOT NULL,
            snapshot_fingerprint TEXT NULL,
            snapshot_version INTEGER NOT NULL DEFAULT 1,
            promoted_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            promoted_at TIMESTAMPTZ NULL,
            failure_reason TEXT NULL,
            metadata_json JSONB NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_oo_promotions_workspace UNIQUE (workspace_id),
            CONSTRAINT chk_oo_promotions_status
                CHECK (status IN ({promotion_statuses_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_promotions_workspace
            ON public.operational_order_promotions (workspace_id)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_documents (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            workspace_id BIGINT NOT NULL
                REFERENCES public.operational_order_draft_workspaces (workspace_id)
                ON DELETE RESTRICT,
            document_kind TEXT NOT NULL DEFAULT 'OPERATIONAL_ORDER',
            status TEXT NOT NULL DEFAULT 'CREATED',
            created_from_workspace_version INTEGER NOT NULL,
            created_from_workspace_fingerprint TEXT NOT NULL,
            promotion_id BIGINT NOT NULL
                REFERENCES public.operational_order_promotions (id)
                ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            version INTEGER NOT NULL DEFAULT 1,
            CONSTRAINT uq_oo_documents_workspace UNIQUE (workspace_id),
            CONSTRAINT chk_oo_documents_status
                CHECK (status IN ({document_statuses_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_documents_workspace
            ON public.operational_order_documents (workspace_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_documents_status
            ON public.operational_order_documents (status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_documents_created_at
            ON public.operational_order_documents (created_at)
        """
    )

    op.execute(
        """
        ALTER TABLE public.operational_order_promotions
            ADD COLUMN IF NOT EXISTS document_id BIGINT NULL
                REFERENCES public.operational_order_documents (id)
                ON DELETE SET NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_promotions_document
            ON public.operational_order_promotions (document_id)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_document_versions (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            document_id BIGINT NOT NULL
                REFERENCES public.operational_order_documents (id)
                ON DELETE CASCADE,
            version_number INTEGER NOT NULL,
            workspace_version INTEGER NOT NULL,
            promotion_snapshot_version INTEGER NOT NULL DEFAULT 1,
            snapshot_fingerprint TEXT NOT NULL,
            is_current BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            CONSTRAINT uq_oo_document_versions_number
                UNIQUE (document_id, version_number)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_document_versions_document
            ON public.operational_order_document_versions (document_id)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_document_localizations (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            document_version_id BIGINT NOT NULL
                REFERENCES public.operational_order_document_versions (id)
                ON DELETE CASCADE,
            locale TEXT NOT NULL,
            block_type TEXT NOT NULL,
            sequence INTEGER NOT NULL DEFAULT 1,
            official_text TEXT NOT NULL,
            content_fingerprint TEXT NOT NULL,
            source_workspace_block_version INTEGER NOT NULL,
            source_confirmation_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            source_reconciliation_id BIGINT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_oo_document_localizations_seq
                UNIQUE (document_version_id, locale, block_type, sequence),
            CONSTRAINT chk_oo_document_localizations_locale
                CHECK (locale IN ({locales_sql})),
            CONSTRAINT chk_oo_document_localizations_block_type
                CHECK (block_type IN ({block_types_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_document_localizations_version
            ON public.operational_order_document_localizations (document_version_id)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_promotion_audit (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            promotion_id BIGINT NOT NULL
                REFERENCES public.operational_order_promotions (id)
                ON DELETE CASCADE,
            action TEXT NOT NULL,
            actor_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            metadata_json JSONB NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_oo_promotion_audit_action
                CHECK (action IN ({promotion_audit_actions_sql}))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_promotion_audit_promotion
            ON public.operational_order_promotion_audit (promotion_id)
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
                'OO-IMP-003 promotion permission ({permission})',
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
    op.execute("DROP TABLE IF EXISTS public.operational_order_promotion_audit CASCADE")
    op.execute("DROP TABLE IF EXISTS public.operational_order_document_localizations CASCADE")
    op.execute("DROP TABLE IF EXISTS public.operational_order_document_versions CASCADE")
    op.execute(
        """
        ALTER TABLE public.operational_order_promotions
            DROP COLUMN IF EXISTS document_id
        """
    )
    op.execute("DROP TABLE IF EXISTS public.operational_order_documents CASCADE")
    op.execute("DROP TABLE IF EXISTS public.operational_order_promotions CASCADE")

    provenance_actions_sql = _in_list(
        (
            "SUBMISSION",
            "ACCEPTANCE",
            "EFFECTIVE_EDIT",
            "BLOCK_ADD",
            "TRANSLATION",
        )
    )
    op.execute(
        """
        ALTER TABLE public.operational_order_text_provenance
            DROP CONSTRAINT IF EXISTS chk_oo_text_provenance_action
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.operational_order_text_provenance
            ADD CONSTRAINT chk_oo_text_provenance_action
                CHECK (action IN ({provenance_actions_sql}))
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
