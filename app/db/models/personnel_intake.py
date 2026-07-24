"""ORM models for Personnel Intake (WP-PPR-INTAKE-001/002, WP-PPR-CARD-COORDINATION-003)."""
from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class PersonnelIntakeLink(Base):
    __tablename__ = "personnel_intake_links"
    __table_args__ = {"schema": "public"}

    link_id = Column(BigInteger, primary_key=True, autoincrement=True)
    application_id = Column(
        BigInteger,
        ForeignKey("public.personnel_applications.application_id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_hash = Column(Text, nullable=False, unique=True)
    token_ciphertext = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'issued'"))
    issued_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    issued_by_user_id = Column(
        BigInteger,
        ForeignKey("public.users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id = Column(
        BigInteger,
        ForeignKey("public.users.user_id", ondelete="RESTRICT"),
        nullable=True,
    )
    superseded_by_link_id = Column(
        BigInteger,
        ForeignKey("public.personnel_intake_links.link_id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class PersonnelIntakeDraft(Base):
    __tablename__ = "personnel_intake_drafts"
    __table_args__ = {"schema": "public"}

    draft_id = Column(BigInteger, primary_key=True, autoincrement=True)
    application_id = Column(
        BigInteger,
        ForeignKey("public.personnel_applications.application_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    link_id = Column(
        BigInteger,
        ForeignKey("public.personnel_intake_links.link_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status = Column(Text, nullable=False, server_default=text("'editable'"))
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class PersonnelIntakeSectionReview(Base):
    __tablename__ = "personnel_intake_section_reviews"
    __table_args__ = {"schema": "public"}

    review_id = Column(BigInteger, primary_key=True, autoincrement=True)
    application_id = Column(
        BigInteger,
        ForeignKey("public.personnel_applications.application_id", ondelete="RESTRICT"),
        nullable=False,
    )
    section_code = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default=text("'pending'"))
    rework_comment = Column(Text, nullable=True)
    reviewed_by_user_id = Column(
        BigInteger,
        ForeignKey("public.users.user_id", ondelete="RESTRICT"),
        nullable=True,
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class PersonnelIntakeTransfer(Base):
    __tablename__ = "personnel_intake_transfers"
    __table_args__ = {"schema": "public"}

    transfer_id = Column(BigInteger, primary_key=True, autoincrement=True)
    application_id = Column(
        BigInteger,
        ForeignKey("public.personnel_applications.application_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    status = Column(Text, nullable=False, server_default=text("'pending'"))
    result = Column(Text, nullable=True)
    transferred_by_user_id = Column(
        BigInteger,
        ForeignKey("public.users.user_id", ondelete="RESTRICT"),
        nullable=True,
    )
    transferred_at = Column(DateTime(timezone=True), nullable=True)
    sections_transferred = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    command_ids = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class PersonnelIntakeReconciliationDecision(Base):
    """Durable per-decision reconciliation store (WP-PPR-CARD-COORDINATION-003)."""

    __tablename__ = "personnel_intake_reconciliation_decisions"
    __table_args__ = {"schema": "public"}

    decision_id = Column(BigInteger, primary_key=True, autoincrement=True)
    application_id = Column(
        BigInteger,
        ForeignKey("public.personnel_applications.application_id", ondelete="RESTRICT"),
        nullable=False,
    )
    person_id = Column(
        BigInteger,
        ForeignKey("public.persons.person_id", ondelete="RESTRICT"),
        nullable=False,
    )
    section_code = Column(Text, nullable=False)
    proposal_index = Column(Integer, nullable=False)
    proposal_fingerprint = Column(Text, nullable=False)
    proposal_payload_digest = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    reason_code = Column(Text, nullable=False)
    evidence = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    target_canonical_record_id = Column(BigInteger, nullable=True)
    expected_row_version = Column(Text, nullable=True)
    expected_canonical_precondition = Column(Text, nullable=False)
    decision_source = Column(Text, nullable=False, server_default=text("'system'"))
    override_token = Column(Text, nullable=True)
    matcher_rule_id = Column(Text, nullable=False)
    matcher_version = Column(Text, nullable=False)
    policy_version = Column(Text, nullable=False)
    digest_algorithm_version = Column(Text, nullable=False)
    idempotency_key = Column(Text, nullable=False, unique=True)
    intent_fingerprint = Column(Text, nullable=False)
    apply_status = Column(Text, nullable=False, server_default=text("'pending'"))
    failure_evidence = Column(JSONB, nullable=True)
    row_version = Column(BigInteger, nullable=False, server_default=text("1"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
