"""Operational orders ORM models (OO-IMP-001 submitted-text intake MVP).

Draft workspace aggregate — separate from official Document Aggregate.
See docs/operational-orders/implementation/OO-IMP-001-submitted-text-intake-mvp.md.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
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

WORKSPACE_STAGES = (
    WORKSPACE_STAGE_SUBMITTED,
    WORKSPACE_STAGE_ACCEPTED,
    WORKSPACE_STAGE_INTAKE_REVIEW,
    WORKSPACE_STAGE_CLARIFICATION_REQUIRED,
    WORKSPACE_STAGE_READY_FOR_EDITORIAL,
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

PROVENANCE_ACTIONS = (
    PROVENANCE_ACTION_SUBMISSION,
    PROVENANCE_ACTION_ACCEPTANCE,
    PROVENANCE_ACTION_EFFECTIVE_EDIT,
    PROVENANCE_ACTION_BLOCK_ADD,
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
