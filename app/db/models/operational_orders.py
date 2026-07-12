"""Operational orders ORM models (OO-IMP-001 intake + OO-IMP-002 editorial + OO-IMP-003 document aggregate).

Draft workspace aggregate — separate from official Document Aggregate.
See docs/operational-orders/implementation/OO-IMP-001-submitted-text-intake-mvp.md,
OO-IMP-002-content-confirmation-translation-workflow.md, and
OO-IMP-003-official-draft-package.md.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

DRAFTING_PATH_SUBMITTED_TEXT = "SUBMITTED_TEXT"

WORKSPACE_STAGE_SUBMITTED = "SUBMITTED"
WORKSPACE_STAGE_ACCEPTED = "ACCEPTED"
WORKSPACE_STAGE_INTAKE_REVIEW = "INTAKE_REVIEW"
WORKSPACE_STAGE_CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
WORKSPACE_STAGE_READY_FOR_EDITORIAL = "READY_FOR_EDITORIAL"
WORKSPACE_STAGE_TRANSLATION_REQUIRED = "TRANSLATION_REQUIRED"
WORKSPACE_STAGE_TRANSLATION_IN_PROGRESS = "TRANSLATION_IN_PROGRESS"
WORKSPACE_STAGE_CONTENT_CONFIRMATION_REQUIRED = "CONTENT_CONFIRMATION_REQUIRED"
WORKSPACE_STAGE_BILINGUAL_RECONCILIATION = "BILINGUAL_RECONCILIATION"
WORKSPACE_STAGE_EDITORIAL_PACKAGE_READY = "EDITORIAL_PACKAGE_READY"
WORKSPACE_STAGE_DOCUMENT_PROMOTED = "DOCUMENT_PROMOTED"

WORKSPACE_STAGES = (
    WORKSPACE_STAGE_SUBMITTED,
    WORKSPACE_STAGE_ACCEPTED,
    WORKSPACE_STAGE_INTAKE_REVIEW,
    WORKSPACE_STAGE_CLARIFICATION_REQUIRED,
    WORKSPACE_STAGE_READY_FOR_EDITORIAL,
    WORKSPACE_STAGE_TRANSLATION_REQUIRED,
    WORKSPACE_STAGE_TRANSLATION_IN_PROGRESS,
    WORKSPACE_STAGE_CONTENT_CONFIRMATION_REQUIRED,
    WORKSPACE_STAGE_BILINGUAL_RECONCILIATION,
    WORKSPACE_STAGE_EDITORIAL_PACKAGE_READY,
    WORKSPACE_STAGE_DOCUMENT_PROMOTED,
)

BLOCK_TYPE_TITLE = "TITLE"
BLOCK_TYPE_PREAMBLE = "PREAMBLE"
BLOCK_TYPE_BODY = "BODY"
BLOCK_TYPE_ORDER_ITEM = "ORDER_ITEM"
BLOCK_TYPE_CONTROL = "CONTROL"
BLOCK_TYPE_ATTACHMENT_REFERENCE = "ATTACHMENT_REFERENCE"
BLOCK_TYPE_SIGNATURE_NOTE = "SIGNATURE_NOTE"
BLOCK_TYPE_OTHER = "OTHER"

BLOCK_TYPES = (
    BLOCK_TYPE_TITLE,
    BLOCK_TYPE_PREAMBLE,
    BLOCK_TYPE_BODY,
    BLOCK_TYPE_ORDER_ITEM,
    BLOCK_TYPE_CONTROL,
    BLOCK_TYPE_ATTACHMENT_REFERENCE,
    BLOCK_TYPE_SIGNATURE_NOTE,
    BLOCK_TYPE_OTHER,
)

LOCALE_RU = "ru"
LOCALE_KK = "kk"
LOCALES = (LOCALE_RU, LOCALE_KK)

STALENESS_CURRENT = "CURRENT"
STALENESS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
STALENESS_STALE = "STALE"

STALENESS_STATES = (
    STALENESS_CURRENT,
    STALENESS_REVIEW_REQUIRED,
    STALENESS_STALE,
)

TEXT_SOURCE_SUBMITTED = "SUBMITTED"
TEXT_SOURCE_OVERRIDE = "OVERRIDE"
TEXT_SOURCE_IMPORTED = "IMPORTED"
TEXT_SOURCE_GENERATED = "GENERATED"

TEXT_SOURCE_TYPES = (
    TEXT_SOURCE_SUBMITTED,
    TEXT_SOURCE_OVERRIDE,
    TEXT_SOURCE_IMPORTED,
    TEXT_SOURCE_GENERATED,
)

PROVENANCE_ACTION_SUBMISSION = "SUBMISSION"
PROVENANCE_ACTION_ACCEPTANCE = "ACCEPTANCE"
PROVENANCE_ACTION_EFFECTIVE_EDIT = "EFFECTIVE_EDIT"
PROVENANCE_ACTION_BLOCK_ADD = "BLOCK_ADD"
PROVENANCE_ACTION_TRANSLATION = "TRANSLATION"
PROVENANCE_ACTION_PROMOTED_FROM_WORKSPACE = "PROMOTED_FROM_WORKSPACE"
PROVENANCE_ACTION_SNAPSHOT_CREATED = "SNAPSHOT_CREATED"
PROVENANCE_ACTION_DOCUMENT_VERSION_CREATED = "DOCUMENT_VERSION_CREATED"
PROVENANCE_ACTION_WORKSPACE_PROMOTED = "WORKSPACE_PROMOTED"
PROVENANCE_ACTION_WORKSPACE_FROZEN = "WORKSPACE_FROZEN"
PROVENANCE_ACTION_PROMOTION_REPLAY = "PROMOTION_REPLAY"
PROVENANCE_ACTION_WORKSPACE_DRIFT_DETECTED = "WORKSPACE_DRIFT_DETECTED"

PROVENANCE_ACTIONS = (
    PROVENANCE_ACTION_SUBMISSION,
    PROVENANCE_ACTION_ACCEPTANCE,
    PROVENANCE_ACTION_EFFECTIVE_EDIT,
    PROVENANCE_ACTION_BLOCK_ADD,
    PROVENANCE_ACTION_TRANSLATION,
    PROVENANCE_ACTION_PROMOTED_FROM_WORKSPACE,
    PROVENANCE_ACTION_SNAPSHOT_CREATED,
    PROVENANCE_ACTION_DOCUMENT_VERSION_CREATED,
    PROVENANCE_ACTION_WORKSPACE_PROMOTED,
    PROVENANCE_ACTION_WORKSPACE_FROZEN,
    PROVENANCE_ACTION_PROMOTION_REPLAY,
    PROVENANCE_ACTION_WORKSPACE_DRIFT_DETECTED,
)

CLARIFICATION_STATUS_OPEN = "OPEN"
CLARIFICATION_STATUS_RESOLVED = "RESOLVED"
CLARIFICATION_STATUS_DISMISSED = "DISMISSED"

CLARIFICATION_STATUSES = (
    CLARIFICATION_STATUS_OPEN,
    CLARIFICATION_STATUS_RESOLVED,
    CLARIFICATION_STATUS_DISMISSED,
)

CLARIFICATION_SEVERITY_ERROR = "ERROR"
CLARIFICATION_SEVERITY_WARNING = "WARNING"
CLARIFICATION_SEVERITY_INFO = "INFO"

CLARIFICATION_SEVERITIES = (
    CLARIFICATION_SEVERITY_ERROR,
    CLARIFICATION_SEVERITY_WARNING,
    CLARIFICATION_SEVERITY_INFO,
)

PARTY_REF_PERSON = "PERSON"
PARTY_REF_POSITION_ROLE = "POSITION_ROLE"
PARTY_REF_ORG_UNIT = "ORG_UNIT"

PARTY_REFERENCE_TYPES = (
    PARTY_REF_PERSON,
    PARTY_REF_POSITION_ROLE,
    PARTY_REF_ORG_UNIT,
)

AUDIT_ACTION_SUBMISSION_CREATED = "SUBMISSION_CREATED"
AUDIT_ACTION_WORKSPACE_ACCEPTED = "WORKSPACE_ACCEPTED"
AUDIT_ACTION_BLOCK_ADDED = "BLOCK_ADDED"
AUDIT_ACTION_EFFECTIVE_TEXT_CHANGED = "EFFECTIVE_TEXT_CHANGED"
AUDIT_ACTION_PROVENANCE_ADDED = "PROVENANCE_ADDED"
AUDIT_ACTION_VALIDATION_EXECUTED = "VALIDATION_EXECUTED"
AUDIT_ACTION_CLARIFICATION_OPENED = "CLARIFICATION_OPENED"
AUDIT_ACTION_CLARIFICATION_RESOLVED = "CLARIFICATION_RESOLVED"
AUDIT_ACTION_READY_FOR_EDITORIAL = "READY_FOR_EDITORIAL"
AUDIT_ACTION_TRANSLATION_REQUESTED = "TRANSLATION_REQUESTED"
AUDIT_ACTION_TRANSLATOR_ASSIGNED = "TRANSLATOR_ASSIGNED"
AUDIT_ACTION_ASSIGNMENT_ACCEPTED = "ASSIGNMENT_ACCEPTED"
AUDIT_ACTION_TRANSLATION_STARTED = "TRANSLATION_STARTED"
AUDIT_ACTION_TRANSLATION_COMPLETED = "TRANSLATION_COMPLETED"
AUDIT_ACTION_CONFIRMATION_CREATED = "CONFIRMATION_CREATED"
AUDIT_ACTION_CONFIRMATION_REVOKED = "CONFIRMATION_REVOKED"
AUDIT_ACTION_CONFIRMATION_SUPERSEDED = "CONFIRMATION_SUPERSEDED"
AUDIT_ACTION_RECONCILIATION_CREATED = "RECONCILIATION_CREATED"
AUDIT_ACTION_RECONCILIATION_INVALIDATED = "RECONCILIATION_INVALIDATED"
AUDIT_ACTION_WORKSPACE_STAGE_CHANGED = "WORKSPACE_STAGE_CHANGED"
AUDIT_ACTION_EDITORIAL_PACKAGE_READY = "EDITORIAL_PACKAGE_READY"
AUDIT_ACTION_EDITORIAL_PACKAGE_VALIDATION_FAILED = "EDITORIAL_PACKAGE_VALIDATION_FAILED"
AUDIT_ACTION_WORKSPACE_FROZEN = "WORKSPACE_FROZEN"
AUDIT_ACTION_PROMOTION_REPLAY = "PROMOTION_REPLAY"
AUDIT_ACTION_REVISION_ADVISORY_RETURNED = "REVISION_ADVISORY_RETURNED"

DRAFT_AUDIT_ACTIONS = (
    AUDIT_ACTION_SUBMISSION_CREATED,
    AUDIT_ACTION_WORKSPACE_ACCEPTED,
    AUDIT_ACTION_BLOCK_ADDED,
    AUDIT_ACTION_EFFECTIVE_TEXT_CHANGED,
    AUDIT_ACTION_PROVENANCE_ADDED,
    AUDIT_ACTION_VALIDATION_EXECUTED,
    AUDIT_ACTION_CLARIFICATION_OPENED,
    AUDIT_ACTION_CLARIFICATION_RESOLVED,
    AUDIT_ACTION_READY_FOR_EDITORIAL,
    AUDIT_ACTION_TRANSLATION_REQUESTED,
    AUDIT_ACTION_TRANSLATOR_ASSIGNED,
    AUDIT_ACTION_ASSIGNMENT_ACCEPTED,
    AUDIT_ACTION_TRANSLATION_STARTED,
    AUDIT_ACTION_TRANSLATION_COMPLETED,
    AUDIT_ACTION_CONFIRMATION_CREATED,
    AUDIT_ACTION_CONFIRMATION_REVOKED,
    AUDIT_ACTION_CONFIRMATION_SUPERSEDED,
    AUDIT_ACTION_RECONCILIATION_CREATED,
    AUDIT_ACTION_RECONCILIATION_INVALIDATED,
    AUDIT_ACTION_WORKSPACE_STAGE_CHANGED,
    AUDIT_ACTION_EDITORIAL_PACKAGE_READY,
    AUDIT_ACTION_EDITORIAL_PACKAGE_VALIDATION_FAILED,
    AUDIT_ACTION_WORKSPACE_FROZEN,
    AUDIT_ACTION_PROMOTION_REPLAY,
    AUDIT_ACTION_REVISION_ADVISORY_RETURNED,
)

ASSIGNMENT_STATUS_REQUESTED = "REQUESTED"
ASSIGNMENT_STATUS_ACCEPTED = "ACCEPTED"
ASSIGNMENT_STATUS_IN_PROGRESS = "IN_PROGRESS"
ASSIGNMENT_STATUS_COMPLETED = "COMPLETED"
ASSIGNMENT_STATUS_CANCELLED = "CANCELLED"
ASSIGNMENT_STATUS_SUPERSEDED = "SUPERSEDED"

ASSIGNMENT_STATUSES = (
    ASSIGNMENT_STATUS_REQUESTED,
    ASSIGNMENT_STATUS_ACCEPTED,
    ASSIGNMENT_STATUS_IN_PROGRESS,
    ASSIGNMENT_STATUS_COMPLETED,
    ASSIGNMENT_STATUS_CANCELLED,
    ASSIGNMENT_STATUS_SUPERSEDED,
)

ASSIGNMENT_ACTIVE_STATUSES = (
    ASSIGNMENT_STATUS_REQUESTED,
    ASSIGNMENT_STATUS_ACCEPTED,
    ASSIGNMENT_STATUS_IN_PROGRESS,
)

CONFIRMATION_ROLE_CONTENT_AUTHOR = "CONTENT_AUTHOR"
CONFIRMATION_ROLE_TRANSLATOR = "TRANSLATOR"
CONFIRMATION_ROLE_DOCUMENT_OPERATOR = "DOCUMENT_OPERATOR"

CONFIRMATION_ROLES = (
    CONFIRMATION_ROLE_CONTENT_AUTHOR,
    CONFIRMATION_ROLE_TRANSLATOR,
    CONFIRMATION_ROLE_DOCUMENT_OPERATOR,
)

CONFIRMATION_STATUS_CONFIRMED = "CONFIRMED"
CONFIRMATION_STATUS_REVOKED = "REVOKED"
CONFIRMATION_STATUS_SUPERSEDED = "SUPERSEDED"

CONFIRMATION_STATUSES = (
    CONFIRMATION_STATUS_CONFIRMED,
    CONFIRMATION_STATUS_REVOKED,
    CONFIRMATION_STATUS_SUPERSEDED,
)

RECONCILIATION_STATUS_PENDING = "PENDING"
RECONCILIATION_STATUS_RECONCILED = "RECONCILED"
RECONCILIATION_STATUS_INVALIDATED = "INVALIDATED"
RECONCILIATION_STATUS_SUPERSEDED = "SUPERSEDED"

RECONCILIATION_STATUSES = (
    RECONCILIATION_STATUS_PENDING,
    RECONCILIATION_STATUS_RECONCILED,
    RECONCILIATION_STATUS_INVALIDATED,
    RECONCILIATION_STATUS_SUPERSEDED,
)

DOCUMENT_KIND_OPERATIONAL_ORDER = "OPERATIONAL_ORDER"

DOCUMENT_STATUS_CREATED = "CREATED"
DOCUMENT_STATUS_READY_FOR_SIGNATURE = "READY_FOR_SIGNATURE"
DOCUMENT_STATUS_SIGNED = "SIGNED"
DOCUMENT_STATUS_REGISTERED = "REGISTERED"
DOCUMENT_STATUS_VOIDED = "VOIDED"

DOCUMENT_STATUSES = (
    DOCUMENT_STATUS_CREATED,
    DOCUMENT_STATUS_READY_FOR_SIGNATURE,
    DOCUMENT_STATUS_SIGNED,
    DOCUMENT_STATUS_REGISTERED,
    DOCUMENT_STATUS_VOIDED,
)

PROMOTION_STATUS_STARTED = "STARTED"
PROMOTION_STATUS_COMPLETED = "COMPLETED"
PROMOTION_STATUS_FAILED = "FAILED"

PROMOTION_STATUSES = (
    PROMOTION_STATUS_STARTED,
    PROMOTION_STATUS_COMPLETED,
    PROMOTION_STATUS_FAILED,
)

PROMOTION_AUDIT_ACTION_STARTED = "PROMOTION_STARTED"
PROMOTION_AUDIT_ACTION_COMPLETED = "PROMOTION_COMPLETED"
PROMOTION_AUDIT_ACTION_FAILED = "PROMOTION_FAILED"
PROMOTION_AUDIT_ACTION_DOCUMENT_CREATED = "DOCUMENT_CREATED"
PROMOTION_AUDIT_ACTION_VERSION_CREATED = "VERSION_CREATED"
PROMOTION_AUDIT_ACTION_LOCALIZATION_SNAPSHOTTED = "LOCALIZATION_SNAPSHOTTED"
PROMOTION_AUDIT_ACTION_WORKSPACE_FROZEN = "WORKSPACE_FROZEN"
PROMOTION_AUDIT_ACTION_PROMOTION_REPLAY = "PROMOTION_REPLAY"
PROMOTION_AUDIT_ACTION_REVISION_ADVISORY_RETURNED = "REVISION_ADVISORY_RETURNED"

PROMOTION_AUDIT_ACTIONS = (
    PROMOTION_AUDIT_ACTION_STARTED,
    PROMOTION_AUDIT_ACTION_COMPLETED,
    PROMOTION_AUDIT_ACTION_FAILED,
    PROMOTION_AUDIT_ACTION_DOCUMENT_CREATED,
    PROMOTION_AUDIT_ACTION_VERSION_CREATED,
    PROMOTION_AUDIT_ACTION_LOCALIZATION_SNAPSHOTTED,
    PROMOTION_AUDIT_ACTION_WORKSPACE_FROZEN,
    PROMOTION_AUDIT_ACTION_PROMOTION_REPLAY,
    PROMOTION_AUDIT_ACTION_REVISION_ADVISORY_RETURNED,
)


class OperationalOrderDraftWorkspace(Base):
    """Draft intake workspace — not an official document aggregate."""

    __tablename__ = "operational_order_draft_workspaces"
    __table_args__ = (
        Index("ix_oo_draft_workspaces_org_stage", "organization_id", "stage"),
        Index("ix_oo_draft_workspaces_submitting_unit", "submitting_org_unit_id"),
        Index("ix_oo_draft_workspaces_created_at", "created_at"),
    )

    workspace_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("org_units.unit_id", ondelete="RESTRICT"), nullable=False
    )
    drafting_path: Mapped[str] = mapped_column(Text, nullable=False, default=DRAFTING_PATH_SUBMITTED_TEXT)
    stage: Mapped[str] = mapped_column(Text, nullable=False, default=WORKSPACE_STAGE_SUBMITTED)
    initiator_type: Mapped[str] = mapped_column(Text, nullable=False)
    initiator_reference: Mapped[str] = mapped_column(Text, nullable=False)
    initiator_display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_author_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_author_reference: Mapped[str] = mapped_column(Text, nullable=False)
    content_author_display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitting_org_unit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("org_units.unit_id", ondelete="RESTRICT"), nullable=False
    )
    record_creator_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    document_operator_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    intended_document_kind: Mapped[str] = mapped_column(Text, nullable=False, default="OPERATIONAL_ORDER")
    proposed_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proposed_signer_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proposed_signer_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proposed_signer_display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_language: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    required_locales: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OperationalOrderDraftBlock(Base):
    """Submitted and effective text block within a draft workspace."""

    __tablename__ = "operational_order_draft_blocks"
    __table_args__ = (
        UniqueConstraint("workspace_id", "locale", "block_type", "sequence", name="uq_oo_draft_blocks_seq"),
        Index("ix_oo_draft_blocks_workspace", "workspace_id"),
    )

    block_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_draft_workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    locale: Mapped[str] = mapped_column(Text, nullable=False)
    block_type: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_text: Mapped[str] = mapped_column(Text, nullable=False)
    workspace_effective_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_type: Mapped[str] = mapped_column(Text, nullable=False, default=TEXT_SOURCE_SUBMITTED)
    review_state: Mapped[str] = mapped_column(Text, nullable=False, default=STALENESS_CURRENT)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OperationalOrderTextProvenance(Base):
    """Append-only provenance for draft text blocks."""

    __tablename__ = "operational_order_text_provenance"
    __table_args__ = (Index("ix_oo_text_provenance_workspace", "workspace_id"),)

    provenance_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_draft_workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    draft_block_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_draft_blocks.block_id", ondelete="CASCADE"),
        nullable=False,
    )
    locale: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_actor_reference: Mapped[str] = mapped_column(Text, nullable=False)
    source_org_unit_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("org_units.unit_id", ondelete="SET NULL"), nullable=True
    )
    source_language: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    derived_from_provenance_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_text_provenance.provenance_id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    content_fingerprint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OperationalOrderClarification(Base):
    """Intake clarification record — not a workflow task."""

    __tablename__ = "operational_order_clarifications"
    __table_args__ = (Index("ix_oo_clarifications_workspace", "workspace_id"),)

    clarification_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_draft_workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    field_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default=CLARIFICATION_STATUS_OPEN)
    requested_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    resolved_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class OperationalOrderDraftAudit(Base):
    """Append-only draft intake audit trail."""

    __tablename__ = "operational_order_draft_audit"
    __table_args__ = (Index("ix_oo_draft_audit_workspace", "workspace_id"),)

    audit_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_draft_workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OperationalOrderTranslationAssignment(Base):
    """Human translation assignment within a draft workspace."""

    __tablename__ = "operational_order_translation_assignments"
    __table_args__ = (
        Index("ix_oo_translation_assignments_workspace", "workspace_id"),
        Index("ix_oo_translation_assignments_status", "workspace_id", "status"),
        Index("ix_oo_translation_assignments_target_locale", "workspace_id", "target_locale"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_draft_workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    source_locale: Mapped[str] = mapped_column(Text, nullable=False)
    target_locale: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_to_type: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_to_reference: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_to_display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default=ASSIGNMENT_STATUS_REQUESTED)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source_block_version: Mapped[int] = mapped_column(Integer, nullable=False)
    target_block_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_content_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    produced_content_fingerprint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OperationalOrderContentConfirmation(Base):
    """Role-bound confirmation of a specific block text version."""

    __tablename__ = "operational_order_content_confirmations"
    __table_args__ = (
        Index("ix_oo_content_confirmations_workspace", "workspace_id"),
        Index("ix_oo_content_confirmations_block", "block_id"),
        Index("ix_oo_content_confirmations_locale", "workspace_id", "locale"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_draft_workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    locale: Mapped[str] = mapped_column(Text, nullable=False)
    block_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_draft_blocks.block_id", ondelete="CASCADE"),
        nullable=False,
    )
    block_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    confirmer_party_type: Mapped[str] = mapped_column(Text, nullable=False)
    confirmer_party_reference: Mapped[str] = mapped_column(Text, nullable=False)
    confirmer_display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmer_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    confirmation_role: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default=CONFIRMATION_STATUS_CONFIRMED)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OperationalOrderBilingualReconciliation(Base):
    """Semantic alignment record for an RU/KK block pair."""

    __tablename__ = "operational_order_bilingual_reconciliations"
    __table_args__ = (Index("ix_oo_bilingual_reconciliations_workspace", "workspace_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_draft_workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    ru_block_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_draft_blocks.block_id", ondelete="CASCADE"),
        nullable=False,
    )
    ru_block_version: Mapped[int] = mapped_column(Integer, nullable=False)
    ru_content_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    kk_block_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_draft_blocks.block_id", ondelete="CASCADE"),
        nullable=False,
    )
    kk_block_version: Mapped[int] = mapped_column(Integer, nullable=False)
    kk_content_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default=RECONCILIATION_STATUS_PENDING)
    reconciled_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    invalidated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OperationalOrderDocument(Base):
    """Official document aggregate root — immutable snapshot after promotion."""

    __tablename__ = "operational_order_documents"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_oo_documents_workspace"),
        Index("ix_oo_documents_workspace", "workspace_id"),
        Index("ix_oo_documents_status", "status"),
        Index("ix_oo_documents_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_draft_workspaces.workspace_id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_kind: Mapped[str] = mapped_column(Text, nullable=False, default=DOCUMENT_KIND_OPERATIONAL_ORDER)
    status: Mapped[str] = mapped_column(Text, nullable=False, default=DOCUMENT_STATUS_CREATED)
    created_from_workspace_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_from_workspace_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    promotion_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_promotions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class OperationalOrderDocumentVersion(Base):
    """Immutable document version snapshot."""

    __tablename__ = "operational_order_document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_oo_document_versions_number"),
        Index("ix_oo_document_versions_document", "document_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    workspace_version: Mapped[int] = mapped_column(Integer, nullable=False)
    promotion_snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snapshot_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )


class OperationalOrderDocumentLocalization(Base):
    """Immutable per-locale block snapshot within a document version."""

    __tablename__ = "operational_order_document_localizations"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id",
            "locale",
            "block_type",
            "sequence",
            name="uq_oo_document_localizations_seq",
        ),
        Index("ix_oo_document_localizations_version", "document_version_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    locale: Mapped[str] = mapped_column(Text, nullable=False)
    block_type: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    official_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    source_workspace_block_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_confirmation_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    source_reconciliation_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OperationalOrderPromotion(Base):
    """Document aggregate factory record — one completed promotion per workspace."""

    __tablename__ = "operational_order_promotions"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_oo_promotions_workspace"),
        Index("ix_oo_promotions_workspace", "workspace_id"),
        Index("ix_oo_promotions_document", "document_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_draft_workspaces.workspace_id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default=PROMOTION_STATUS_STARTED)
    workspace_version: Mapped[int] = mapped_column(Integer, nullable=False)
    workspace_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_fingerprint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    promoted_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OperationalOrderPromotionAudit(Base):
    """Append-only promotion audit trail."""

    __tablename__ = "operational_order_promotion_audit"
    __table_args__ = (Index("ix_oo_promotion_audit_promotion", "promotion_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    promotion_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_promotions.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
