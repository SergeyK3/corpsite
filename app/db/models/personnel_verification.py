"""ORM models for managed personnel verification (ADR-060 / WP-VER-002)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
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

CONTROL_POINT_EMPLOYMENT_EPISODE = "employment_episode"
CONTROL_POINT_MEDICAL_CATEGORY = "medical_category"
ALLOWED_CONTROL_POINTS = (
    CONTROL_POINT_EMPLOYMENT_EPISODE,
    CONTROL_POINT_MEDICAL_CATEGORY,
)

OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT = "person_external_employment"

POLICY_STATUS_DRAFT = "draft"
POLICY_STATUS_ACTIVE = "active"
POLICY_STATUS_INACTIVE = "inactive"
POLICY_STATUSES = (
    POLICY_STATUS_DRAFT,
    POLICY_STATUS_ACTIVE,
    POLICY_STATUS_INACTIVE,
)

TASK_STATUS_PENDING = "pending"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_REJECTED = "rejected"
TASK_STATUS_CANCELLED = "cancelled"
TASK_STATUSES = (
    TASK_STATUS_PENDING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_REJECTED,
    TASK_STATUS_CANCELLED,
)
OPEN_TASK_STATUSES = (TASK_STATUS_PENDING,)
TERMINAL_TASK_STATUSES = (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_REJECTED,
    TASK_STATUS_CANCELLED,
)

ATTESTATION_DECISION_VERIFIED = "verified"
ATTESTATION_DECISION_REJECTED = "rejected"
ATTESTATION_DECISIONS = (
    ATTESTATION_DECISION_VERIFIED,
    ATTESTATION_DECISION_REJECTED,
)


class VerificationPolicy(Base):
    """Versioned personnel verification control policy."""

    __tablename__ = "verification_policies"
    __table_args__ = (
        UniqueConstraint("control_point", "policy_version", name="uq_vp_control_point_version"),
        Index(
            "uq_vp_one_active_per_control_point",
            "control_point",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_vp_status_effective", "status", "effective_from", "effective_to"),
    )

    policy_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    control_point: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    decision_basis: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    published_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class VerificationTask(Base):
    """HR verification work item for a controlled record revision."""

    __tablename__ = "verification_tasks"
    __table_args__ = (
        Index(
            "uq_vt_one_pending_per_version_policy",
            "object_type",
            "object_version_id",
            "policy_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_vt_person_status", "person_id", "status", "control_point"),
        Index("ix_vt_object_version", "object_type", "object_id", "object_version_id"),
    )

    task_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("persons.person_id", ondelete="RESTRICT"), nullable=False
    )
    control_point: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    object_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    policy_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("verification_policies.policy_id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class VerificationAttestation(Base):
    """Immutable verification decision for a controlled record revision."""

    __tablename__ = "verification_attestations"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_va_task_id"),
        Index("ix_va_person_decided", "person_id", "decided_at"),
        Index("ix_va_object_version", "object_type", "object_id", "object_version_id"),
    )

    attestation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("verification_tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
    )
    person_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("persons.person_id", ondelete="RESTRICT"), nullable=False
    )
    control_point: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    object_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    policy_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("verification_policies.policy_id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    verifier_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    verifier_employee_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("employees.employee_id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
