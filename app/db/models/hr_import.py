"""HR import staging ORM models (ADR-038 Phase 2A)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
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
CLASSIFICATION_PART_TIME = "PART_TIME"

REVIEW_STATUS_PENDING = "PENDING"
REVIEW_STATUS_APPROVED = "APPROVED"
REVIEW_STATUS_REJECTED = "REJECTED"
REVIEW_STATUS_MERGED = "MERGED"


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


class HrImportRow(Base):
    """Parsed row from an HR import batch."""

    __tablename__ = "hr_import_rows"
    __table_args__ = (
        UniqueConstraint("batch_id", "source_sheet", "source_row_number", name="uq_hr_import_rows_source"),
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


class HrImportDocumentCandidate(Base):
    """Proposed professional document parsed from import row text."""

    __tablename__ = "hr_import_document_candidates"
    __table_args__ = (
        Index("ix_hr_import_document_candidates_row", "row_id"),
        Index("ix_hr_import_document_candidates_employee", "employee_id"),
        Index("ix_hr_import_document_candidates_review", "review_status"),
    )

    candidate_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
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
    proposed_document_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parsed_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    parsed_valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    review_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PENDING'"))
    created_document_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("employee_documents.document_id", ondelete="SET NULL"),
        nullable=True,
    )
