"""Operational order archive import staging models (WP-PO-002 Stage 2A)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


IMPORT_BATCH_STATUS_IMPORTED = "IMPORTED"
IMPORT_BATCH_STATUS_IN_REVIEW = "IN_REVIEW"
IMPORT_BATCH_STATUS_COMPLETED = "COMPLETED"
IMPORT_BATCH_STATUS_CANCELLED = "CANCELLED"
IMPORT_BATCH_STATUSES = (
    IMPORT_BATCH_STATUS_IMPORTED,
    IMPORT_BATCH_STATUS_IN_REVIEW,
    IMPORT_BATCH_STATUS_COMPLETED,
    IMPORT_BATCH_STATUS_CANCELLED,
)

INITIAL_REVIEW_REQUISITES_PRECONFIRMED = "REQUISITES_PRECONFIRMED"
INITIAL_REVIEW_NEEDS_REQUISITES = "NEEDS_REQUISITES"
INITIAL_REVIEW_NEEDS_DOCUMENT_TYPE = "NEEDS_DOCUMENT_TYPE"
INITIAL_REVIEW_POSSIBLE_NON_ORDER = "POSSIBLE_NON_ORDER"
INITIAL_REVIEW_STATES = (
    INITIAL_REVIEW_REQUISITES_PRECONFIRMED,
    INITIAL_REVIEW_NEEDS_REQUISITES,
    INITIAL_REVIEW_NEEDS_DOCUMENT_TYPE,
    INITIAL_REVIEW_POSSIBLE_NON_ORDER,
)

REVIEW_OUTCOME_CONFIRMED = "CONFIRMED"
REVIEW_OUTCOME_NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
REVIEW_OUTCOME_DRAFT_ORDER = "DRAFT_ORDER"
REVIEW_OUTCOME_ORDER_ANNEX = "ORDER_ANNEX"
REVIEW_OUTCOME_SUPPORTING_DOCUMENT = "SUPPORTING_DOCUMENT"
REVIEW_OUTCOME_DUPLICATE = "DUPLICATE"
REVIEW_OUTCOME_NOT_AN_ORDER = "NOT_AN_ORDER"
REVIEW_OUTCOMES = (
    REVIEW_OUTCOME_CONFIRMED,
    REVIEW_OUTCOME_NEEDS_CLARIFICATION,
    REVIEW_OUTCOME_DRAFT_ORDER,
    REVIEW_OUTCOME_ORDER_ANNEX,
    REVIEW_OUTCOME_SUPPORTING_DOCUMENT,
    REVIEW_OUTCOME_DUPLICATE,
    REVIEW_OUTCOME_NOT_AN_ORDER,
)


class OperationalOrderImportBatch(Base):
    """One idempotent archive manifest staging batch."""

    __tablename__ = "operational_order_import_batches"
    __table_args__ = (
        UniqueConstraint("batch_fingerprint", name="uq_oo_import_batches_fingerprint"),
        CheckConstraint(
            "status IN ('IMPORTED', 'IN_REVIEW', 'COMPLETED', 'CANCELLED')",
            name="chk_oo_import_batches_status",
        ),
        CheckConstraint(
            "total_rows >= 0 AND valid_rows >= 0 AND error_rows >= 0 "
            "AND total_rows = valid_rows + error_rows "
            "AND file_count >= 0 AND file_count <= total_rows "
            "AND archive_section_count >= 0",
            name="chk_oo_import_batches_counts",
        ),
        CheckConstraint(
            "btrim(source_manifest_name) <> '' "
            "AND position('/' in source_manifest_name) = 0 "
            "AND position(chr(92) in source_manifest_name) = 0",
            name="chk_oo_import_batches_manifest_name",
        ),
        CheckConstraint(
            "source_manifest_sha256 ~ '^[0-9a-f]{64}$'",
            name="chk_oo_import_batches_manifest_sha256",
        ),
        CheckConstraint(
            "batch_fingerprint ~ '^[0-9a-f]{64}$'",
            name="chk_oo_import_batches_fingerprint",
        ),
        CheckConstraint(
            "btrim(format_version) <> ''",
            name="chk_oo_import_batches_format_version",
        ),
        CheckConstraint(
            "btrim(source_root_name) <> '' "
            "AND position('/' in source_root_name) = 0 "
            "AND position(chr(92) in source_root_name) = 0",
            name="chk_oo_import_batches_root_name",
        ),
        CheckConstraint("btrim(sheet_name) <> ''", name="chk_oo_import_batches_sheet_name"),
        Index("ix_oo_import_batches_status", "status"),
        Index("ix_oo_import_batches_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_manifest_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_manifest_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    batch_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    format_version: Mapped[str] = mapped_column(Text, nullable=False)
    source_root_name: Mapped[str] = mapped_column(Text, nullable=False)
    sheet_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=IMPORT_BATCH_STATUS_IMPORTED,
        server_default=text("'IMPORTED'"),
    )
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    archive_section_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class OperationalOrderImportRow(Base):
    """Immutable source snapshot plus mutable review fields for one manifest row."""

    __tablename__ = "operational_order_import_rows"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "source_row_number",
            name="uq_oo_import_rows_batch_source_row",
        ),
        UniqueConstraint(
            "batch_id",
            "relative_path",
            name="uq_oo_import_rows_batch_relative_path",
        ),
        CheckConstraint(
            "initial_review_state IN "
            "('REQUISITES_PRECONFIRMED', 'NEEDS_REQUISITES', "
            "'NEEDS_DOCUMENT_TYPE', 'POSSIBLE_NON_ORDER')",
            name="chk_oo_import_rows_initial_review_state",
        ),
        CheckConstraint(
            "source_status IN "
            "('Найден', 'Не найден', 'Требует проверки', 'Не является приказом')",
            name="chk_oo_import_rows_source_status",
        ),
        CheckConstraint(
            "btrim(source_row_number) <> ''",
            name="chk_oo_import_rows_source_row_number",
        ),
        CheckConstraint(
            "btrim(source_filename) <> ''",
            name="chk_oo_import_rows_source_filename",
        ),
        CheckConstraint(
            "btrim(relative_path) <> ''",
            name="chk_oo_import_rows_relative_path",
        ),
        CheckConstraint(
            "file_extension IN ('.doc', '.docx', '.pdf')",
            name="chk_oo_import_rows_file_extension",
        ),
        CheckConstraint("file_size >= 0", name="chk_oo_import_rows_file_size"),
        CheckConstraint(
            "file_sha256 ~ '^[0-9a-f]{64}$'",
            name="chk_oo_import_rows_file_sha256",
        ),
        CheckConstraint("version > 0", name="chk_oo_import_rows_version"),
        CheckConstraint(
            "review_outcome IS NULL OR review_outcome IN "
            "('CONFIRMED', 'NEEDS_CLARIFICATION', 'DRAFT_ORDER', 'ORDER_ANNEX', "
            "'SUPPORTING_DOCUMENT', 'DUPLICATE', 'NOT_AN_ORDER')",
            name="chk_oo_import_rows_review_outcome",
        ),
        CheckConstraint(
            "review_outcome <> 'CONFIRMED' OR ("
            "confirmed_document_type IS NOT NULL AND "
            "btrim(confirmed_document_type) <> '' AND "
            "confirmed_order_number IS NOT NULL AND "
            "btrim(confirmed_order_number) <> '' AND "
            "confirmed_order_date IS NOT NULL AND "
            "confirmed_subject IS NOT NULL AND "
            "btrim(confirmed_subject) <> '')",
            name="chk_oo_import_rows_confirmed_fields",
        ),
        CheckConstraint(
            "review_outcome IS NULL OR review_outcome = 'CONFIRMED' "
            "OR (review_comment IS NOT NULL AND btrim(review_comment) <> '')",
            name="chk_oo_import_rows_review_comment",
        ),
        CheckConstraint(
            "review_outcome IS NULL OR review_outcome = 'CONFIRMED' OR ("
            "confirmed_document_type IS NULL AND "
            "confirmed_order_number IS NULL AND "
            "confirmed_order_date IS NULL AND "
            "confirmed_subject IS NULL)",
            name="chk_oo_import_rows_nonconfirmed_fields",
        ),
        Index("ix_oo_import_rows_batch", "batch_id"),
        Index("ix_oo_import_rows_file_sha256", "file_sha256"),
        Index("ix_oo_import_rows_initial_review", "initial_review_state"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_import_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_row_number: Mapped[str] = mapped_column(Text, nullable=False)
    source_filename: Mapped[str] = mapped_column(Text, nullable=False)
    source_document_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_status: Mapped[str] = mapped_column(Text, nullable=False)
    source_event_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_order_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_order_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_folder: Mapped[str] = mapped_column(Text, nullable=False)
    archive_section: Mapped[str] = mapped_column(Text, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_extension: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    initial_review_state: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_document_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmed_order_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmed_order_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    confirmed_subject: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    official_document_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("operational_order_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
