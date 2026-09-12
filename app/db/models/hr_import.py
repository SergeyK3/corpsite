"""HR import staging ORM models (ADR-038 Phase 2A)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SOURCE_TYPE_HR_CONTROL_LIST = "HR_CONTROL_LIST"

BATCH_STATUS_UPLOADED = "UPLOADED"
BATCH_STATUS_PARSED = "PARSED"
BATCH_STATUS_IN_REVIEW = "IN_REVIEW"
BATCH_STATUS_APPLY_PENDING = "APPLY_PENDING"
BATCH_STATUS_APPLIED = "APPLIED"
BATCH_STATUS_PARTIALLY_APPLIED = "PARTIALLY_APPLIED"
BATCH_STATUS_FAILED = "FAILED"
BATCH_STATUS_CANCELLED = "CANCELLED"

MATCH_STATUS_NOT_PROCESSED = "NOT_PROCESSED"
MATCH_STATUS_AUTO = "AUTO_MATCH"
MATCH_STATUS_REVIEW = "REVIEW_REQUIRED"
MATCH_STATUS_NO_MATCH = "NO_MATCH"
MATCH_STATUS_INVALID = "INVALID_DATA"
MATCH_STATUS_SKIPPED = "SKIPPED"

CLASSIFICATION_NORMAL = "NORMAL"
CLASSIFICATION_INVALID_IIN = "INVALID_IIN"
CLASSIFICATION_DUPLICATE_IIN = "DUPLICATE_IIN"
CLASSIFICATION_DECLARATION = "DECLARATION"
CLASSIFICATION_SUMMARY_ROW = "SUMMARY_ROW"
CLASSIFICATION_CATEGORY_ROW = "CATEGORY_ROW"
CLASSIFICATION_PART_TIME = "PART_TIME"

ROW_TYPE_EMPLOYEE = "EMPLOYEE"
ROW_TYPE_CATEGORY_ROW = "CATEGORY_ROW"
ROW_TYPE_SUMMARY_ROW = "SUMMARY_ROW"
ROW_TYPE_DECLARATION_PERSON = "DECLARATION_PERSON"
ROW_TYPE_DECLARATION_ROW = "DECLARATION_ROW"

REVIEW_STATUS_PENDING = "PENDING"
REVIEW_STATUS_APPROVED = "APPROVED"
REVIEW_STATUS_REJECTED = "REJECTED"
REVIEW_STATUS_MERGED = "MERGED"

# Identity-quality review foundation (IQ-2).  These constants deliberately
# describe only persisted state; parser classification and HR actions arrive in
# later packages.
IDENTITY_QUALITY_STATE_UNRESOLVED = "UNRESOLVED"
IDENTITY_QUALITY_STATE_RESOLVED = "RESOLVED"
IDENTITY_QUALITY_STATE_DEFERRED = "DEFERRED"
IDENTITY_QUALITY_STATES = (
    IDENTITY_QUALITY_STATE_UNRESOLVED,
    IDENTITY_QUALITY_STATE_RESOLVED,
    IDENTITY_QUALITY_STATE_DEFERRED,
)
IDENTITY_QUALITY_REASON_IIN_MISSING = "IIN_MISSING"
IDENTITY_QUALITY_REASON_IIN_INVALID_FORMAT = "IIN_INVALID_FORMAT"
IDENTITY_QUALITY_REASON_IIN_UNMATCHED = "IIN_UNMATCHED"
IDENTITY_QUALITY_REASON_IIN_CONFIRMED = "IIN_CONFIRMED"
IDENTITY_QUALITY_REASON_IIN_DEFERRED = "IIN_DEFERRED"
IDENTITY_QUALITY_REASON_CODES = (
    IDENTITY_QUALITY_REASON_IIN_MISSING,
    IDENTITY_QUALITY_REASON_IIN_INVALID_FORMAT,
    IDENTITY_QUALITY_REASON_IIN_UNMATCHED,
    IDENTITY_QUALITY_REASON_IIN_CONFIRMED,
    IDENTITY_QUALITY_REASON_IIN_DEFERRED,
)
IDENTITY_REVIEW_EVENT_IIN_CONFIRMED = "IIN_CONFIRMED"
IDENTITY_REVIEW_EVENT_PERSON_EMPLOYEE_LINK_CONFIRMED = "PERSON_EMPLOYEE_LINK_CONFIRMED"
IDENTITY_REVIEW_EVENT_DEFERRED = "DEFERRED"
IDENTITY_REVIEW_EVENT_SYSTEM_IIN_MISSING = "SYSTEM_IIN_MISSING"
IDENTITY_REVIEW_EVENT_SYSTEM_IIN_INVALID_FORMAT = "SYSTEM_IIN_INVALID_FORMAT"
IDENTITY_REVIEW_EVENT_SYSTEM_IIN_UNMATCHED = "SYSTEM_IIN_UNMATCHED"
IDENTITY_REVIEW_EVENT_TYPES = (
    IDENTITY_REVIEW_EVENT_IIN_CONFIRMED,
    IDENTITY_REVIEW_EVENT_PERSON_EMPLOYEE_LINK_CONFIRMED,
    IDENTITY_REVIEW_EVENT_DEFERRED,
    IDENTITY_REVIEW_EVENT_SYSTEM_IIN_MISSING,
    IDENTITY_REVIEW_EVENT_SYSTEM_IIN_INVALID_FORMAT,
    IDENTITY_REVIEW_EVENT_SYSTEM_IIN_UNMATCHED,
)
IDENTITY_REVIEW_ACTOR_SYSTEM = "SYSTEM"
IDENTITY_REVIEW_ACTOR_HR = "HR"
IDENTITY_REVIEW_ACTOR_TYPES = (IDENTITY_REVIEW_ACTOR_SYSTEM, IDENTITY_REVIEW_ACTOR_HR)
IDENTITY_QUALITY_POLICY_V1 = "IDENTITY_QUALITY_V1"
IDENTITY_QUALITY_POLICY_CODES = (IDENTITY_QUALITY_POLICY_V1,)


class HrImportBatch(Base):
    """Uploaded HR import file batch metadata."""

    __tablename__ = "hr_import_batches"
    __table_args__ = (
        Index("ix_hr_import_batches_status", "status"),
        Index("ix_hr_import_batches_imported_by", "imported_by"),
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    import_code: Mapped[str] = mapped_column(Text, nullable=False)
    imported_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'UPLOADED'"))
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_file_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)


class HrImportRow(Base):
    """Parsed row from an HR import batch."""

    __tablename__ = "hr_import_rows"
    __table_args__ = (
        UniqueConstraint("batch_id", "source_sheet", "source_row_number", name="uq_hr_import_rows_source"),
        # Allows IQ-2 child tables to prove their row belongs to their batch.
        UniqueConstraint("batch_id", "row_id", name="uq_hr_import_rows_batch_row"),
        Index("ix_hr_import_rows_batch", "batch_id"),
        Index("ix_hr_import_rows_match_status", "batch_id", "match_status"),
    )

    row_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("hr_import_batches.batch_id", ondelete="CASCADE"),
        nullable=False,
    )
    source_sheet: Mapped[str] = mapped_column(Text, nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    normalized_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    match_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'NOT_PROCESSED'"))
    review_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_codes: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("employees.employee_id", ondelete="SET NULL"),
        nullable=True,
    )


class HrImportIdentityQualityState(Base):
    """Materialized current identity-quality state; no historical-row backfill."""

    __tablename__ = "hr_import_identity_quality_states"
    __table_args__ = (
        UniqueConstraint("batch_id", "row_id", name="uq_hr_import_identity_quality_states_batch_row"),
        ForeignKeyConstraint(
            ["batch_id", "row_id"], ["hr_import_rows.batch_id", "hr_import_rows.row_id"],
            name="fk_hr_import_iq_state_batch_row", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "person_id"], ["employees.employee_id", "employees.person_id"],
            name="fk_hr_import_iq_state_employee_person", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["current_event_id", "batch_id", "row_id", "source_row_fingerprint", "identity_state", "reason_code"],
            ["hr_import_identity_review_events.event_id", "hr_import_identity_review_events.batch_id", "hr_import_identity_review_events.row_id", "hr_import_identity_review_events.source_row_fingerprint", "hr_import_identity_review_events.resulting_state", "hr_import_identity_review_events.reason_code"],
            name="fk_hr_import_iq_state_effective_event", ondelete="RESTRICT", deferrable=True, initially="DEFERRED",
        ),
        CheckConstraint(
            "(identity_state = 'UNRESOLVED' AND reason_code IN ('IIN_MISSING', 'IIN_INVALID_FORMAT', 'IIN_UNMATCHED') AND person_id IS NULL AND employee_id IS NULL) "
            "OR (identity_state = 'RESOLVED' AND reason_code = 'IIN_CONFIRMED' AND person_id IS NOT NULL AND employee_id IS NOT NULL) "
            "OR (identity_state = 'DEFERRED' AND reason_code = 'IIN_DEFERRED' AND person_id IS NULL AND employee_id IS NULL)",
            name="chk_hr_import_iq_state_reason_binding",
        ),
        CheckConstraint("source_row_fingerprint ~ '^[0-9a-f]{64}$'", name="chk_hr_import_iq_state_source_fp"),
        CheckConstraint("normalized_payload_fingerprint ~ '^[0-9a-f]{64}$'", name="chk_hr_import_iq_state_payload_fp"),
        CheckConstraint("row_version >= 1 AND source_version >= 1", name="chk_hr_import_iq_state_versions"),
        CheckConstraint("policy_version IN ('IDENTITY_QUALITY_V1')", name="chk_hr_import_iq_state_policy"),
        Index(
            "ix_hr_import_identity_quality_queue", "batch_id", "identity_state", "reason_code", "row_id",
            postgresql_where=text("identity_state IN ('UNRESOLVED', 'DEFERRED')"),
        ),
    )

    state_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    row_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_event_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    identity_state: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    person_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    employee_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_row_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_payload_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    row_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class HrImportIdentityReviewEvent(Base):
    """PII-free, database-enforced append-only identity-review decision event."""

    __tablename__ = "hr_import_identity_review_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["batch_id", "row_id"], ["hr_import_rows.batch_id", "hr_import_rows.row_id"],
            name="fk_hr_import_iq_event_batch_row", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["batch_id", "row_id"], ["hr_import_identity_quality_states.batch_id", "hr_import_identity_quality_states.row_id"],
            name="fk_hr_import_iq_event_current_state", ondelete="RESTRICT", deferrable=True, initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["employee_id", "person_id"], ["employees.employee_id", "employees.person_id"],
            name="fk_hr_import_iq_event_employee_person", ondelete="RESTRICT",
        ),
        UniqueConstraint("event_id", "batch_id", "row_id", "source_row_fingerprint", "resulting_state", "reason_code", name="uq_hr_import_iq_event_effective"),
        CheckConstraint(
            "(event_type = 'SYSTEM_IIN_MISSING' AND actor_type = 'SYSTEM' AND actor_user_id IS NULL AND resulting_state = 'UNRESOLVED' AND reason_code = 'IIN_MISSING' AND person_id IS NULL AND employee_id IS NULL AND original_iin_fingerprint IS NULL AND entered_iin_fingerprint IS NULL) "
            "OR (event_type = 'SYSTEM_IIN_INVALID_FORMAT' AND actor_type = 'SYSTEM' AND actor_user_id IS NULL AND resulting_state = 'UNRESOLVED' AND reason_code = 'IIN_INVALID_FORMAT' AND person_id IS NULL AND employee_id IS NULL AND original_iin_fingerprint IS NOT NULL AND entered_iin_fingerprint IS NULL) "
            "OR (event_type = 'SYSTEM_IIN_UNMATCHED' AND actor_type = 'SYSTEM' AND actor_user_id IS NULL AND resulting_state = 'UNRESOLVED' AND reason_code = 'IIN_UNMATCHED' AND person_id IS NULL AND employee_id IS NULL AND original_iin_fingerprint IS NOT NULL AND entered_iin_fingerprint IS NULL) "
            "OR (event_type = 'IIN_CONFIRMED' AND actor_type = 'HR' AND actor_user_id IS NOT NULL AND resulting_state = 'UNRESOLVED' AND reason_code = 'IIN_UNMATCHED' AND person_id IS NULL AND employee_id IS NULL AND original_iin_fingerprint IS NOT NULL AND entered_iin_fingerprint IS NOT NULL) "
            "OR (event_type = 'PERSON_EMPLOYEE_LINK_CONFIRMED' AND actor_type = 'HR' AND actor_user_id IS NOT NULL AND resulting_state = 'RESOLVED' AND reason_code = 'IIN_CONFIRMED' AND person_id IS NOT NULL AND employee_id IS NOT NULL AND original_iin_fingerprint IS NOT NULL AND entered_iin_fingerprint IS NOT NULL) "
            "OR (event_type = 'DEFERRED' AND actor_type = 'HR' AND actor_user_id IS NOT NULL AND resulting_state = 'DEFERRED' AND reason_code = 'IIN_DEFERRED' AND person_id IS NULL AND employee_id IS NULL AND entered_iin_fingerprint IS NULL)",
            name="chk_hr_import_iq_event_decision",
        ),
        CheckConstraint("original_iin_fingerprint IS NULL OR original_iin_fingerprint ~ '^[0-9a-f]{64}$'", name="chk_hr_import_iq_event_original_iin_fp"),
        CheckConstraint("entered_iin_fingerprint IS NULL OR entered_iin_fingerprint ~ '^[0-9a-f]{64}$'", name="chk_hr_import_iq_event_entered_iin_fp"),
        CheckConstraint("source_row_fingerprint ~ '^[0-9a-f]{64}$'", name="chk_hr_import_iq_event_source_fp"),
        CheckConstraint("before_normalized_payload_fingerprint ~ '^[0-9a-f]{64}$'", name="chk_hr_import_iq_event_before_payload_fp"),
        CheckConstraint("after_normalized_payload_fingerprint ~ '^[0-9a-f]{64}$'", name="chk_hr_import_iq_event_after_payload_fp"),
        CheckConstraint("row_version >= 1 AND source_version >= 1", name="chk_hr_import_iq_event_versions"),
        CheckConstraint("policy_version IN ('IDENTITY_QUALITY_V1')", name="chk_hr_import_iq_event_policy"),
        Index("ix_hr_import_identity_review_events_row_occurred", "batch_id", "row_id", text("occurred_at DESC"), text("event_id DESC")),
    )

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, unique=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    row_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    resulting_state: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    person_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    employee_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    original_iin_fingerprint: Mapped[str | None] = mapped_column(Text)
    entered_iin_fingerprint: Mapped[str | None] = mapped_column(Text)
    source_row_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    before_normalized_payload_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    after_normalized_payload_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    row_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class HrImportDocumentCandidate(Base):
    """Proposed professional document parsed from import row text."""

    __tablename__ = "hr_import_document_candidates"
    __table_args__ = (
        Index("ix_hr_import_document_candidates_row", "row_id"),
        Index("ix_hr_import_document_candidates_batch", "batch_id"),
        Index("ix_hr_import_document_candidates_employee", "employee_id"),
        Index("ix_hr_import_document_candidates_review", "review_status"),
        Index("ix_hr_import_document_candidates_batch_kind", "batch_id", "document_kind"),
    )

    candidate_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("hr_import_batches.batch_id", ondelete="CASCADE"),
        nullable=False,
    )
    row_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("hr_import_rows.row_id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("employees.employee_id", ondelete="SET NULL"),
        nullable=True,
    )
    employee_identity_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("employee_identities.identity_id", ondelete="SET NULL"),
        nullable=True,
    )
    full_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    iin: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    department: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'training'"))
    proposed_document_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    organization: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parsed_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    parsed_issued_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    parsed_valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    specialty: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    certificate_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    source_sheet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_row: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    external_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    storage_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    storage_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fragment_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    parse_method: Mapped[Optional[str]] = mapped_column(Text, nullable=True, server_default=text("'regex_v1'"))
    source_field: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    review_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PENDING'"))
    created_document_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("employee_documents.document_id", ondelete="SET NULL"),
        nullable=True,
    )
