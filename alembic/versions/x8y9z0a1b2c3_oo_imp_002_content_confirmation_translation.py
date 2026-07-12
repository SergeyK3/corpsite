"""OO-IMP-002 — Content confirmation and translation workflow."""
from __future__ import annotations

from alembic import op

revision = "x8y9z0a1b2c3"
down_revision = "w7x8y9z0a1b2"
branch_labels = None
depends_on = None

_WORKSPACE_STAGES = (
    "SUBMITTED",
    "ACCEPTED",
    "INTAKE_REVIEW",
    "CLARIFICATION_REQUIRED",
    "READY_FOR_EDITORIAL",
    "TRANSLATION_REQUIRED",
    "TRANSLATION_IN_PROGRESS",
    "CONTENT_CONFIRMATION_REQUIRED",
    "BILINGUAL_RECONCILIATION",
    "EDITORIAL_PACKAGE_READY",
)
_PROVENANCE_ACTIONS = (
    "SUBMISSION",
    "ACCEPTANCE",
    "EFFECTIVE_EDIT",
    "BLOCK_ADD",
    "TRANSLATION",
)
_DRAFT_AUDIT_ACTIONS = (
    "SUBMISSION_CREATED",
    "WORKSPACE_ACCEPTED",
    "BLOCK_ADDED",
    "EFFECTIVE_TEXT_CHANGED",
    "PROVENANCE_ADDED",
    "VALIDATION_EXECUTED",
    "CLARIFICATION_OPENED",
    "CLARIFICATION_RESOLVED",
    "READY_FOR_EDITORIAL",
    "TRANSLATION_REQUESTED",
    "TRANSLATOR_ASSIGNED",
    "ASSIGNMENT_ACCEPTED",
    "TRANSLATION_STARTED",
    "TRANSLATION_COMPLETED",
    "CONFIRMATION_CREATED",
    "CONFIRMATION_REVOKED",
    "CONFIRMATION_SUPERSEDED",
    "RECONCILIATION_CREATED",
    "RECONCILIATION_INVALIDATED",
    "WORKSPACE_STAGE_CHANGED",
    "EDITORIAL_PACKAGE_READY",
    "EDITORIAL_PACKAGE_VALIDATION_FAILED",
)
_ASSIGNMENT_STATUSES = (
    "REQUESTED",
    "ACCEPTED",
    "IN_PROGRESS",
    "COMPLETED",
    "CANCELLED",
    "SUPERSEDED",
)
_CONFIRMATION_ROLES = ("CONTENT_AUTHOR", "TRANSLATOR", "DOCUMENT_OPERATOR")
_CONFIRMATION_STATUSES = ("CONFIRMED", "REVOKED", "SUPERSEDED")
_RECONCILIATION_STATUSES = ("PENDING", "RECONCILED", "INVALIDATED", "SUPERSEDED")
_LOCALES = ("ru", "kk")
_PARTY_TYPES = ("PERSON", "POSITION_ROLE", "ORG_UNIT")
_OO_PERMISSIONS = (
    "OPERATIONAL_ORDERS_TRANSLATION_ASSIGN",
    "OPERATIONAL_ORDERS_TRANSLATION_WORK",
    "OPERATIONAL_ORDERS_CONTENT_CONFIRM",
    "OPERATIONAL_ORDERS_RECONCILE",
    "OPERATIONAL_ORDERS_EDITORIAL_READY",
)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    stages_sql = _in_list(_WORKSPACE_STAGES)
    provenance_actions_sql = _in_list(_PROVENANCE_ACTIONS)
    audit_actions_sql = _in_list(_DRAFT_AUDIT_ACTIONS)
    assignment_statuses_sql = _in_list(_ASSIGNMENT_STATUSES)
    confirmation_roles_sql = _in_list(_CONFIRMATION_ROLES)
    confirmation_statuses_sql = _in_list(_CONFIRMATION_STATUSES)
    reconciliation_statuses_sql = _in_list(_RECONCILIATION_STATUSES)
    locales_sql = _in_list(_LOCALES)
    party_types_sql = _in_list(_PARTY_TYPES)

    op.execute(
        """
        ALTER TABLE public.operational_order_draft_workspaces
            DROP CONSTRAINT IF EXISTS chk_oo_draft_workspaces_stage
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.operational_order_draft_workspaces
            ADD CONSTRAINT chk_oo_draft_workspaces_stage
                CHECK (stage IN ({stages_sql}))
        """
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

    op.execute(
        """
        ALTER TABLE public.operational_order_draft_audit
            DROP CONSTRAINT IF EXISTS chk_oo_draft_audit_action
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.operational_order_draft_audit
            ADD CONSTRAINT chk_oo_draft_audit_action
                CHECK (action IN ({audit_actions_sql}))
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_translation_assignments (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            workspace_id BIGINT NOT NULL
                REFERENCES public.operational_order_draft_workspaces (workspace_id)
                ON DELETE CASCADE,
            source_locale TEXT NOT NULL,
            target_locale TEXT NOT NULL,
            assigned_to_type TEXT NOT NULL,
            assigned_to_reference TEXT NOT NULL,
            assigned_to_display_name TEXT NULL,
            assigned_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            status TEXT NOT NULL DEFAULT 'REQUESTED',
            requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            accepted_at TIMESTAMPTZ NULL,
            completed_at TIMESTAMPTZ NULL,
            cancelled_at TIMESTAMPTZ NULL,
            due_at TIMESTAMPTZ NULL,
            source_block_version INTEGER NOT NULL,
            target_block_version INTEGER NULL,
            source_content_fingerprint TEXT NOT NULL,
            produced_content_fingerprint TEXT NULL,
            notes TEXT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_oo_translation_assignments_source_locale
                CHECK (source_locale IN ({locales_sql})),
            CONSTRAINT chk_oo_translation_assignments_target_locale
                CHECK (target_locale IN ({locales_sql})),
            CONSTRAINT chk_oo_translation_assignments_assigned_to_type
                CHECK (assigned_to_type IN ({party_types_sql})),
            CONSTRAINT chk_oo_translation_assignments_status
                CHECK (status IN ({assignment_statuses_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_translation_assignments_workspace
            ON public.operational_order_translation_assignments (workspace_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_translation_assignments_status
            ON public.operational_order_translation_assignments (workspace_id, status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_translation_assignments_target_locale
            ON public.operational_order_translation_assignments (workspace_id, target_locale)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_oo_translation_active_target_locale
            ON public.operational_order_translation_assignments (workspace_id, target_locale)
            WHERE status IN ('REQUESTED', 'ACCEPTED', 'IN_PROGRESS')
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_content_confirmations (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            workspace_id BIGINT NOT NULL
                REFERENCES public.operational_order_draft_workspaces (workspace_id)
                ON DELETE CASCADE,
            locale TEXT NOT NULL,
            block_id BIGINT NOT NULL
                REFERENCES public.operational_order_draft_blocks (block_id)
                ON DELETE CASCADE,
            block_version INTEGER NOT NULL,
            content_fingerprint TEXT NOT NULL,
            confirmer_party_type TEXT NOT NULL,
            confirmer_party_reference TEXT NOT NULL,
            confirmer_display_name TEXT NULL,
            confirmer_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            confirmation_role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'CONFIRMED',
            confirmed_at TIMESTAMPTZ NULL,
            revoked_at TIMESTAMPTZ NULL,
            revocation_reason TEXT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_oo_content_confirmations_locale
                CHECK (locale IN ({locales_sql})),
            CONSTRAINT chk_oo_content_confirmations_party_type
                CHECK (confirmer_party_type IN ({party_types_sql})),
            CONSTRAINT chk_oo_content_confirmations_role
                CHECK (confirmation_role IN ({confirmation_roles_sql})),
            CONSTRAINT chk_oo_content_confirmations_status
                CHECK (status IN ({confirmation_statuses_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_content_confirmations_workspace
            ON public.operational_order_content_confirmations (workspace_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_content_confirmations_block
            ON public.operational_order_content_confirmations (block_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_content_confirmations_locale
            ON public.operational_order_content_confirmations (workspace_id, locale)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_bilingual_reconciliations (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            workspace_id BIGINT NOT NULL
                REFERENCES public.operational_order_draft_workspaces (workspace_id)
                ON DELETE CASCADE,
            ru_block_id BIGINT NOT NULL
                REFERENCES public.operational_order_draft_blocks (block_id)
                ON DELETE CASCADE,
            ru_block_version INTEGER NOT NULL,
            ru_content_fingerprint TEXT NOT NULL,
            kk_block_id BIGINT NOT NULL
                REFERENCES public.operational_order_draft_blocks (block_id)
                ON DELETE CASCADE,
            kk_block_version INTEGER NOT NULL,
            kk_content_fingerprint TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            reconciled_by_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            reconciled_at TIMESTAMPTZ NULL,
            notes TEXT NULL,
            invalidated_at TIMESTAMPTZ NULL,
            invalidation_reason TEXT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_oo_bilingual_reconciliations_status
                CHECK (status IN ({reconciliation_statuses_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_bilingual_reconciliations_workspace
            ON public.operational_order_bilingual_reconciliations (workspace_id)
        """
    )

    for permission_code in _OO_PERMISSIONS:
        display_name = permission_code.replace("_", " ").title()
        op.execute(
            f"""
            INSERT INTO public.access_roles (
                code, name, description, access_level, level_rank, is_system
            )
            VALUES (
                '{permission_code}',
                '{display_name}',
                'OO-IMP-002 editorial workflow permission ({permission_code})',
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
    for permission_code in reversed(_OO_PERMISSIONS):
        op.execute(
            f"""
            DELETE FROM public.access_grants g
            USING public.access_roles ar
            WHERE g.access_role_id = ar.access_role_id
              AND ar.code = '{permission_code}'
            """
        )
        op.execute(
            f"""
            DELETE FROM public.access_roles ar
            WHERE ar.code = '{permission_code}'
            """
        )

    op.execute("DROP TABLE IF EXISTS public.operational_order_bilingual_reconciliations CASCADE")
    op.execute("DROP TABLE IF EXISTS public.operational_order_content_confirmations CASCADE")
    op.execute("DROP TABLE IF EXISTS public.operational_order_translation_assignments CASCADE")

    old_stages_sql = _in_list(
        (
            "SUBMITTED",
            "ACCEPTED",
            "INTAKE_REVIEW",
            "CLARIFICATION_REQUIRED",
            "READY_FOR_EDITORIAL",
        )
    )
    old_provenance_sql = _in_list(("SUBMISSION", "ACCEPTANCE", "EFFECTIVE_EDIT", "BLOCK_ADD"))
    old_audit_sql = _in_list(
        (
            "SUBMISSION_CREATED",
            "WORKSPACE_ACCEPTED",
            "BLOCK_ADDED",
            "EFFECTIVE_TEXT_CHANGED",
            "PROVENANCE_ADDED",
            "VALIDATION_EXECUTED",
            "CLARIFICATION_OPENED",
            "CLARIFICATION_RESOLVED",
            "READY_FOR_EDITORIAL",
        )
    )

    op.execute(
        """
        UPDATE public.operational_order_draft_workspaces
        SET stage = 'READY_FOR_EDITORIAL'
        WHERE stage IN (
            'TRANSLATION_REQUIRED',
            'TRANSLATION_IN_PROGRESS',
            'CONTENT_CONFIRMATION_REQUIRED',
            'BILINGUAL_RECONCILIATION',
            'EDITORIAL_PACKAGE_READY'
        )
        """
    )

    op.execute(
        """
        ALTER TABLE public.operational_order_draft_workspaces
            DROP CONSTRAINT IF EXISTS chk_oo_draft_workspaces_stage
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.operational_order_draft_workspaces
            ADD CONSTRAINT chk_oo_draft_workspaces_stage
                CHECK (stage IN ({old_stages_sql}))
        """
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
                CHECK (action IN ({old_provenance_sql}))
        """
    )

    op.execute(
        """
        ALTER TABLE public.operational_order_draft_audit
            DROP CONSTRAINT IF EXISTS chk_oo_draft_audit_action
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.operational_order_draft_audit
            ADD CONSTRAINT chk_oo_draft_audit_action
                CHECK (action IN ({old_audit_sql}))
        """
    )
