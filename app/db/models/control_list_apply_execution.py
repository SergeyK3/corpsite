"""Control List apply execution ORM models (WP-CL-012)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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

APPLY_RUN_STATUS_PENDING = "pending"
APPLY_RUN_STATUS_RUNNING = "running"
APPLY_RUN_STATUS_SUCCEEDED = "succeeded"
APPLY_RUN_STATUS_PARTIALLY_SUCCEEDED = "partially_succeeded"
APPLY_RUN_STATUS_FAILED = "failed"
APPLY_RUN_STATUS_CANCELLED = "cancelled"

APPLY_ACTION_STATUS_PENDING = "pending"
APPLY_ACTION_STATUS_RUNNING = "running"
APPLY_ACTION_STATUS_SUCCEEDED = "succeeded"
APPLY_ACTION_STATUS_SKIPPED = "skipped"
APPLY_ACTION_STATUS_DEFERRED = "deferred"
APPLY_ACTION_STATUS_FAILED = "failed"


class ControlListApplyRun(Base):
    __tablename__ = "control_list_apply_runs"
    __table_args__ = (
        CheckConstraint("length(trim(review_run_key)) > 0", name="chk_control_list_apply_runs_review_run_key_nonempty"),
        CheckConstraint("length(trim(plan_key)) > 0", name="chk_control_list_apply_runs_plan_key_nonempty"),
        CheckConstraint(
            "length(plan_fingerprint) = 64 AND plan_fingerprint ~ '^[0-9a-f]{64}$'",
            name="chk_control_list_apply_runs_plan_fingerprint_format",
        ),
        Index("ix_control_list_apply_runs_import_run", "import_run_id", "created_at"),
        Index("ix_control_list_apply_runs_status", "status", "created_at"),
        Index("uq_control_list_apply_runs_plan_fingerprint", "plan_fingerprint", unique=True),
    )

    apply_run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    import_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("control_list_import_runs.import_run_id", ondelete="RESTRICT"),
        nullable=False,
    )
    review_run_key: Mapped[str] = mapped_column(Text, nullable=False)
    plan_key: Mapped[str] = mapped_column(Text, nullable=False)
    plan_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    plan_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=APPLY_RUN_STATUS_PENDING)
    requested_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ControlListApplyAction(Base):
    __tablename__ = "control_list_apply_actions"
    __table_args__ = (
        UniqueConstraint("apply_run_id", "action_index", name="uq_control_list_apply_actions_run_index"),
        UniqueConstraint("idempotency_key", name="uq_control_list_apply_actions_idempotency_key"),
        CheckConstraint("action_index >= 0", name="chk_control_list_apply_actions_action_index"),
        CheckConstraint("attempt_count >= 0", name="chk_control_list_apply_actions_attempt_count"),
        Index("ix_control_list_apply_actions_run", "apply_run_id", "action_index"),
        Index("ix_control_list_apply_actions_status", "status", "updated_at"),
    )

    apply_action_execution_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    apply_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("control_list_apply_runs.apply_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    action_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_aggregate: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    action_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=APPLY_ACTION_STATUS_PENDING)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
