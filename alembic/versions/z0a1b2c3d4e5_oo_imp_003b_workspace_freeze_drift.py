"""OO-IMP-003B — Workspace freeze, fingerprint drift detection and revision advisory."""
from __future__ import annotations

from alembic import op

revision = "z0a1b2c3d4e5"
down_revision = "y9z0a1b2c3d4"
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
    "DOCUMENT_PROMOTED",
)
_PROVENANCE_ACTIONS = (
    "SUBMISSION",
    "ACCEPTANCE",
    "EFFECTIVE_EDIT",
    "BLOCK_ADD",
    "TRANSLATION",
    "PROMOTED_FROM_WORKSPACE",
    "SNAPSHOT_CREATED",
    "DOCUMENT_VERSION_CREATED",
    "WORKSPACE_PROMOTED",
    "WORKSPACE_FROZEN",
    "PROMOTION_REPLAY",
    "WORKSPACE_DRIFT_DETECTED",
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
    "WORKSPACE_FROZEN",
    "PROMOTION_REPLAY",
    "REVISION_ADVISORY_RETURNED",
)
_PROMOTION_AUDIT_ACTIONS = (
    "PROMOTION_STARTED",
    "PROMOTION_COMPLETED",
    "PROMOTION_FAILED",
    "DOCUMENT_CREATED",
    "VERSION_CREATED",
    "LOCALIZATION_SNAPSHOTTED",
    "WORKSPACE_FROZEN",
    "PROMOTION_REPLAY",
    "REVISION_ADVISORY_RETURNED",
)

_PREV_WORKSPACE_STAGES = tuple(stage for stage in _WORKSPACE_STAGES if stage != "DOCUMENT_PROMOTED")
_PREV_PROVENANCE_ACTIONS = tuple(
    action
    for action in _PROVENANCE_ACTIONS
    if action
    not in (
        "WORKSPACE_PROMOTED",
        "WORKSPACE_FROZEN",
        "PROMOTION_REPLAY",
        "WORKSPACE_DRIFT_DETECTED",
    )
)
_PREV_DRAFT_AUDIT_ACTIONS = tuple(
    action
    for action in _DRAFT_AUDIT_ACTIONS
    if action not in ("WORKSPACE_FROZEN", "PROMOTION_REPLAY", "REVISION_ADVISORY_RETURNED")
)
_PREV_PROMOTION_AUDIT_ACTIONS = tuple(
    action
    for action in _PROMOTION_AUDIT_ACTIONS
    if action not in ("WORKSPACE_FROZEN", "PROMOTION_REPLAY", "REVISION_ADVISORY_RETURNED")
)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    stages_sql = _in_list(_WORKSPACE_STAGES)
    provenance_actions_sql = _in_list(_PROVENANCE_ACTIONS)
    audit_actions_sql = _in_list(_DRAFT_AUDIT_ACTIONS)
    promotion_audit_actions_sql = _in_list(_PROMOTION_AUDIT_ACTIONS)

    op.execute(
        """
        UPDATE public.operational_order_draft_workspaces AS w
        SET stage = 'DOCUMENT_PROMOTED'
        WHERE stage <> 'DOCUMENT_PROMOTED'
          AND EXISTS (
              SELECT 1
              FROM public.operational_order_documents AS d
              INNER JOIN public.operational_order_promotions AS p
                ON p.id = d.promotion_id
               AND p.workspace_id = d.workspace_id
              INNER JOIN public.operational_order_document_versions AS v
                ON v.document_id = d.id
               AND v.version_number = 1
              WHERE d.workspace_id = w.workspace_id
                AND p.status = 'COMPLETED'
                AND p.document_id = d.id
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
        """
        ALTER TABLE public.operational_order_promotion_audit
            DROP CONSTRAINT IF EXISTS chk_oo_promotion_audit_action
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.operational_order_promotion_audit
            ADD CONSTRAINT chk_oo_promotion_audit_action
                CHECK (action IN ({promotion_audit_actions_sql}))
        """
    )


def downgrade() -> None:
    prev_stages_sql = _in_list(_PREV_WORKSPACE_STAGES)
    prev_provenance_sql = _in_list(_PREV_PROVENANCE_ACTIONS)
    prev_audit_sql = _in_list(_PREV_DRAFT_AUDIT_ACTIONS)
    prev_promotion_audit_sql = _in_list(_PREV_PROMOTION_AUDIT_ACTIONS)

    op.execute(
        """
        UPDATE public.operational_order_draft_workspaces
        SET stage = 'EDITORIAL_PACKAGE_READY'
        WHERE stage = 'DOCUMENT_PROMOTED'
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
                CHECK (stage IN ({prev_stages_sql}))
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
                CHECK (action IN ({prev_provenance_sql}))
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
                CHECK (action IN ({prev_audit_sql}))
        """
    )

    op.execute(
        """
        ALTER TABLE public.operational_order_promotion_audit
            DROP CONSTRAINT IF EXISTS chk_oo_promotion_audit_action
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.operational_order_promotion_audit
            ADD CONSTRAINT chk_oo_promotion_audit_action
                CHECK (action IN ({prev_promotion_audit_sql}))
        """
    )
