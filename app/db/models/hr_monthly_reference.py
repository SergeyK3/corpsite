"""ORM models for Monthly Reference Dataset (ADR-058 / WP-MRD-001)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SOURCE_TYPE_HR_CONTROL_LIST = "HR_CONTROL_LIST"

MRD_STATUS_ACTIVE = "ACTIVE"
MRD_STATUS_CLOSED = "CLOSED"

DIFFERENCE_LIFECYCLE_DETECTED = "DETECTED"
DIFFERENCE_LIFECYCLE_CONFIRMED = "CONFIRMED"
DIFFERENCE_LIFECYCLE_REJECTED = "REJECTED"
DIFFERENCE_LIFECYCLE_SUPERSEDED = "SUPERSEDED"

DIFFERENCE_BUSINESS_NEVER_CONFIRMED = "NEVER_CONFIRMED"
DIFFERENCE_BUSINESS_PERIOD_CHANGED = "PERIOD_CHANGED"

TECHNICAL_DIFF_NEW = "NEW"
TECHNICAL_DIFF_CHANGED = "CHANGED"
TECHNICAL_DIFF_REMOVED = "REMOVED"
TECHNICAL_DIFF_CONFLICT = "CONFLICT"

ORIGIN_IMPORT_COMPARE = "IMPORT_COMPARE"
ORIGIN_MANUAL_EDIT = "MANUAL_EDIT"
ORIGIN_SYSTEM_RECALC = "SYSTEM_RECALC"
ORIGIN_MRD_FORK = "MRD_FORK"
ORIGIN_DATA_REPAIR = "DATA_REPAIR"

COMPARISON_RUN_RUNNING = "RUNNING"
COMPARISON_RUN_COMPLETED = "COMPLETED"
COMPARISON_RUN_FAILED = "FAILED"
COMPARISON_RUN_CANCELLED = "CANCELLED"

REFERENCE_EVENT_FORK_VERSION = "FORK_VERSION"
REFERENCE_EVENT_FORK_PERIOD = "FORK_PERIOD"
REFERENCE_EVENT_CLOSE = "CLOSE"
REFERENCE_EVENT_ACTIVATE = "ACTIVATE"
REFERENCE_EVENT_CREATE = "CREATE"

MRD_COMMAND_FORK_VERSION = "FORK_VERSION"
MRD_COMMAND_FORK_PERIOD = "FORK_PERIOD"

MRD_COMMAND_EXECUTION_PENDING = "pending"
MRD_COMMAND_EXECUTION_COMPLETED = "completed"

MRD_RECORD_KINDS = frozenset(
    {"roster", "training", "certificate", "category", "education"}
)


class HrDifferenceOriginType(Base):
    """Extensible Difference Origin registry."""

    __tablename__ = "hr_difference_origin_types"

    origin_code: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class HrMonthlyReference(Base):
    """MRD version container for a report period."""

    __tablename__ = "hr_monthly_references"
    __table_args__ = (
        UniqueConstraint("report_period", "version", name="uq_hmr_report_period_version"),
        Index(
            "uq_hmr_one_active_per_period",
            "report_period",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_hmr_report_period_status", "report_period", "status", "version"),
    )

    mrd_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_period: Mapped[date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'ACTIVE'"))
    source_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{SOURCE_TYPE_HR_CONTROL_LIST}'"),
    )
    forked_from_reference_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_monthly_references.mrd_id", ondelete="RESTRICT"),
        nullable=True,
    )
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_batch_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_import_batches.batch_id", ondelete="SET NULL"),
        nullable=True,
    )
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class HrComparisonRun(Base):
    """Automatic Comparison run audit metadata."""

    __tablename__ = "hr_comparison_runs"
    __table_args__ = (
        Index("ix_hcr_batch_started", "batch_id", "started_at"),
        Index("ix_hcr_mrd_started", "mrd_id", "started_at"),
    )

    comparison_run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    batch_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_import_batches.batch_id", ondelete="SET NULL"),
        nullable=True,
    )
    mrd_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("hr_monthly_references.mrd_id", ondelete="RESTRICT"),
        nullable=False,
    )
    report_period: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'RUNNING'"))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class HrDetectedDifference(Base):
    """Persistent Detected Difference with lifecycle and origin."""

    __tablename__ = "hr_detected_differences"
    __table_args__ = (
        Index(
            "uq_hdd_one_open_detected_per_logical_key",
            "report_period",
            "mrd_id",
            "logical_key",
            unique=True,
            postgresql_where=text("lifecycle_status = 'DETECTED'"),
        ),
        Index(
            "ix_hdd_queue_detected",
            "report_period",
            "lifecycle_status",
            "detected_at",
            postgresql_where=text("lifecycle_status = 'DETECTED'"),
        ),
        Index("ix_hdd_origin", "difference_origin_code", "lifecycle_status"),
        Index(
            "ix_hdd_supersedes",
            "supersedes_difference_id",
            postgresql_where=text("supersedes_difference_id IS NOT NULL"),
        ),
    )

    difference_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_period: Mapped[date] = mapped_column(Date, nullable=False)
    mrd_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("hr_monthly_references.mrd_id", ondelete="RESTRICT"),
        nullable=False,
    )
    logical_key: Mapped[str] = mapped_column(Text, nullable=False)
    entity_scope: Mapped[str] = mapped_column(Text, nullable=False)
    record_kind: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attribute: Mapped[str] = mapped_column(Text, nullable=False)
    business_type: Mapped[str] = mapped_column(Text, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{DIFFERENCE_LIFECYCLE_DETECTED}'"),
    )
    technical_diff_class: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difference_origin_code: Mapped[str] = mapped_column(
        Text,
        ForeignKey("hr_difference_origin_types.origin_code", ondelete="RESTRICT"),
        nullable=False,
    )
    origin_context: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    old_value: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    supersedes_difference_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_detected_differences.difference_id", ondelete="RESTRICT"),
        nullable=True,
    )
    last_comparison_run_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_comparison_runs.comparison_run_id", ondelete="SET NULL"),
        nullable=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    reject_basis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class HrConfirmedChange(Base):
    """Append-only Confirmed Change event log."""

    __tablename__ = "hr_confirmed_changes"
    __table_args__ = (
        UniqueConstraint("detected_difference_id", name="uq_hcc_one_event_per_difference"),
        Index("ix_hcc_report_period_confirmed_at", "report_period", "confirmed_at"),
        Index("ix_hcc_mrd_confirmed_at", "mrd_id", "confirmed_at"),
    )

    confirmed_change_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    detected_difference_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("hr_detected_differences.difference_id", ondelete="RESTRICT"),
        nullable=False,
    )
    report_period: Mapped[date] = mapped_column(Date, nullable=False)
    mrd_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("hr_monthly_references.mrd_id", ondelete="RESTRICT"),
        nullable=False,
    )
    entity_scope: Mapped[str] = mapped_column(Text, nullable=False)
    attribute: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    confirmed_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    basis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difference_origin_code: Mapped[str] = mapped_column(
        Text,
        ForeignKey("hr_difference_origin_types.origin_code", ondelete="RESTRICT"),
        nullable=False,
    )
    origin_context: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    source_batch_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_import_batches.batch_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class HrMonthlyReferenceEntry(Base):
    """Confirmed MRD state entry."""

    __tablename__ = "hr_monthly_reference_entries"
    __table_args__ = (
        UniqueConstraint("mrd_id", "match_key", name="uq_hmre_mrd_match_key"),
        Index("ix_hmre_mrd_id", "mrd_id"),
        Index("ix_hmre_canonical_hash", "mrd_id", "canonical_hash"),
        Index(
            "ix_hmre_employee_id",
            "mrd_id",
            "employee_id",
            postgresql_where=text("employee_id IS NOT NULL"),
        ),
    )

    entry_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mrd_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("hr_monthly_references.mrd_id", ondelete="RESTRICT"),
        nullable=False,
    )
    entity_scope: Mapped[str] = mapped_column(Text, nullable=False)
    record_kind: Mapped[str] = mapped_column(Text, nullable=False)
    match_key: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_hash: Mapped[str] = mapped_column(Text, nullable=False)
    employee_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("employees.employee_id", ondelete="SET NULL"),
        nullable=True,
    )
    iin: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    effective_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    source_row_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_import_rows.row_id", ondelete="SET NULL"),
        nullable=True,
    )
    source_normalized_record_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    last_confirmed_change_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_confirmed_changes.confirmed_change_id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class HrReferenceVersionEvent(Base):
    """MRD fork/close/activate version event journal."""

    __tablename__ = "hr_reference_version_events"
    __table_args__ = (
        Index("ix_hrve_mrd_performed_at", "mrd_id", "performed_at"),
        Index("ix_hrve_report_period_performed_at", "report_period", "performed_at"),
    )

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    report_period: Mapped[date] = mapped_column(Date, nullable=False)
    mrd_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("hr_monthly_references.mrd_id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_mrd_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_monthly_references.mrd_id", ondelete="RESTRICT"),
        nullable=True,
    )
    performed_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    event_context: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
