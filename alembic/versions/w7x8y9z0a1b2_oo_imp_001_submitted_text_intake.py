"""OO-IMP-001 — Operational orders submitted-text intake foundation."""
from __future__ import annotations

from alembic import op

revision = "w7x8y9z0a1b2"
down_revision = "v6w7x8y9z0a1"
branch_labels = None
depends_on = None

_WORKSPACE_STAGES = (
    "SUBMITTED",
    "ACCEPTED",
    "INTAKE_REVIEW",
    "CLARIFICATION_REQUIRED",
    "READY_FOR_EDITORIAL",
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
_STALENESS = ("CURRENT", "REVIEW_REQUIRED", "STALE")
_TEXT_SOURCES = ("SUBMITTED", "OVERRIDE", "IMPORTED", "GENERATED")
_PROVENANCE_ACTIONS = ("SUBMISSION", "ACCEPTANCE", "EFFECTIVE_EDIT", "BLOCK_ADD")
_CLARIFICATION_STATUSES = ("OPEN", "RESOLVED", "DISMISSED")
_CLARIFICATION_SEVERITIES = ("ERROR", "WARNING", "INFO")
_PARTY_TYPES = ("PERSON", "POSITION_ROLE", "ORG_UNIT")
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
)
_OO_PERMISSIONS = (
    "OPERATIONAL_ORDERS_INTAKE_CREATE",
    "OPERATIONAL_ORDERS_INTAKE_READ",
    "OPERATIONAL_ORDERS_INTAKE_OPERATE",
)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    stages_sql = _in_list(_WORKSPACE_STAGES)
    block_types_sql = _in_list(_BLOCK_TYPES)
    locales_sql = _in_list(_LOCALES)
    staleness_sql = _in_list(_STALENESS)
    text_sources_sql = _in_list(_TEXT_SOURCES)
    provenance_actions_sql = _in_list(_PROVENANCE_ACTIONS)
    clarification_statuses_sql = _in_list(_CLARIFICATION_STATUSES)
    clarification_severities_sql = _in_list(_CLARIFICATION_SEVERITIES)
    party_types_sql = _in_list(_PARTY_TYPES)
    audit_actions_sql = _in_list(_DRAFT_AUDIT_ACTIONS)

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_draft_workspaces (
            workspace_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            organization_id BIGINT NOT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            drafting_path TEXT NOT NULL DEFAULT 'SUBMITTED_TEXT',
            stage TEXT NOT NULL DEFAULT 'SUBMITTED',
            initiator_type TEXT NOT NULL,
            initiator_reference TEXT NOT NULL,
            initiator_display_name TEXT NULL,
            content_author_type TEXT NOT NULL,
            content_author_reference TEXT NOT NULL,
            content_author_display_name TEXT NULL,
            submitting_org_unit_id BIGINT NOT NULL
                REFERENCES public.org_units (unit_id) ON DELETE RESTRICT,
            record_creator_user_id BIGINT NOT NULL
                REFERENCES public.users (user_id) ON DELETE RESTRICT,
            document_operator_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            intended_document_kind TEXT NOT NULL DEFAULT 'OPERATIONAL_ORDER',
            proposed_title TEXT NULL,
            proposed_signer_type TEXT NULL,
            proposed_signer_reference TEXT NULL,
            proposed_signer_display_name TEXT NULL,
            source_language TEXT NULL,
            required_locales JSONB NOT NULL DEFAULT '["ru","kk"]'::jsonb,
            submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            accepted_at TIMESTAMPTZ NULL,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_oo_draft_workspaces_drafting_path
                CHECK (drafting_path = 'SUBMITTED_TEXT'),
            CONSTRAINT chk_oo_draft_workspaces_stage
                CHECK (stage IN ({stages_sql})),
            CONSTRAINT chk_oo_draft_workspaces_initiator_type
                CHECK (initiator_type IN ({party_types_sql})),
            CONSTRAINT chk_oo_draft_workspaces_content_author_type
                CHECK (content_author_type IN ({party_types_sql})),
            CONSTRAINT chk_oo_draft_workspaces_proposed_signer_type
                CHECK (
                    proposed_signer_type IS NULL
                    OR proposed_signer_type IN ({party_types_sql})
                ),
            CONSTRAINT chk_oo_draft_workspaces_source_language
                CHECK (source_language IS NULL OR source_language IN ({locales_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_draft_workspaces_org_stage
            ON public.operational_order_draft_workspaces (organization_id, stage)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_draft_workspaces_submitting_unit
            ON public.operational_order_draft_workspaces (submitting_org_unit_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_draft_workspaces_created_at
            ON public.operational_order_draft_workspaces (created_at DESC)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_draft_blocks (
            block_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            workspace_id BIGINT NOT NULL
                REFERENCES public.operational_order_draft_workspaces (workspace_id)
                ON DELETE CASCADE,
            locale TEXT NOT NULL,
            block_type TEXT NOT NULL,
            submitted_text TEXT NOT NULL,
            workspace_effective_text TEXT NULL,
            sequence INTEGER NOT NULL DEFAULT 1,
            source_type TEXT NOT NULL DEFAULT 'SUBMITTED',
            review_state TEXT NOT NULL DEFAULT 'CURRENT',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_oo_draft_blocks_seq
                UNIQUE (workspace_id, locale, block_type, sequence),
            CONSTRAINT chk_oo_draft_blocks_locale
                CHECK (locale IN ({locales_sql})),
            CONSTRAINT chk_oo_draft_blocks_block_type
                CHECK (block_type IN ({block_types_sql})),
            CONSTRAINT chk_oo_draft_blocks_source_type
                CHECK (source_type IN ({text_sources_sql})),
            CONSTRAINT chk_oo_draft_blocks_review_state
                CHECK (review_state IN ({staleness_sql})),
            CONSTRAINT chk_oo_draft_blocks_submitted_text_nonempty
                CHECK (btrim(submitted_text) <> '')
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_draft_blocks_workspace
            ON public.operational_order_draft_blocks (workspace_id)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_text_provenance (
            provenance_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            workspace_id BIGINT NOT NULL
                REFERENCES public.operational_order_draft_workspaces (workspace_id)
                ON DELETE CASCADE,
            draft_block_id BIGINT NOT NULL
                REFERENCES public.operational_order_draft_blocks (block_id)
                ON DELETE CASCADE,
            locale TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_actor_type TEXT NOT NULL,
            source_actor_reference TEXT NOT NULL,
            source_org_unit_id BIGINT NULL
                REFERENCES public.org_units (unit_id) ON DELETE SET NULL,
            source_language TEXT NULL,
            derived_from_provenance_id BIGINT NULL
                REFERENCES public.operational_order_text_provenance (provenance_id)
                ON DELETE SET NULL,
            action TEXT NOT NULL,
            content_fingerprint TEXT NULL,
            metadata_json JSONB NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_oo_text_provenance_locale
                CHECK (locale IN ({locales_sql})),
            CONSTRAINT chk_oo_text_provenance_source_type
                CHECK (source_type IN ({text_sources_sql})),
            CONSTRAINT chk_oo_text_provenance_actor_type
                CHECK (source_actor_type IN ({party_types_sql})),
            CONSTRAINT chk_oo_text_provenance_action
                CHECK (action IN ({provenance_actions_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_text_provenance_workspace
            ON public.operational_order_text_provenance (workspace_id)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_clarifications (
            clarification_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            workspace_id BIGINT NOT NULL
                REFERENCES public.operational_order_draft_workspaces (workspace_id)
                ON DELETE CASCADE,
            code TEXT NOT NULL,
            severity TEXT NOT NULL,
            category TEXT NOT NULL,
            message TEXT NOT NULL,
            field_path TEXT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN',
            requested_by BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            resolved_by BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            resolution_note TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolved_at TIMESTAMPTZ NULL,
            CONSTRAINT chk_oo_clarifications_status
                CHECK (status IN ({clarification_statuses_sql})),
            CONSTRAINT chk_oo_clarifications_severity
                CHECK (severity IN ({clarification_severities_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_clarifications_workspace
            ON public.operational_order_clarifications (workspace_id)
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.operational_order_draft_audit (
            audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            workspace_id BIGINT NOT NULL
                REFERENCES public.operational_order_draft_workspaces (workspace_id)
                ON DELETE CASCADE,
            action TEXT NOT NULL,
            actor_user_id BIGINT NULL
                REFERENCES public.users (user_id) ON DELETE SET NULL,
            metadata_json JSONB NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_oo_draft_audit_action
                CHECK (action IN ({audit_actions_sql}))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oo_draft_audit_workspace
            ON public.operational_order_draft_audit (workspace_id)
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
                'OO-IMP-001 bootstrap permission ({permission_code})',
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

    op.execute("DROP TABLE IF EXISTS public.operational_order_draft_audit CASCADE")
    op.execute("DROP TABLE IF EXISTS public.operational_order_clarifications CASCADE")
    op.execute("DROP TABLE IF EXISTS public.operational_order_text_provenance CASCADE")
    op.execute("DROP TABLE IF EXISTS public.operational_order_draft_blocks CASCADE")
    op.execute("DROP TABLE IF EXISTS public.operational_order_draft_workspaces CASCADE")
