"""WP-PPR-MIG-005F-A immutable correction event and operational outbox models."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

PPR_CORRECTION_EVENT_TYPE = "PPR_SECTION_MANUAL_CORRECTED"
PPR_CORRECTION_SECTIONS = ("general", "education", "training")
PPR_CORRECTION_ORIGIN_STATUSES = ("REVIEW_REQUIRED", "ERROR")
PPR_CORRECTION_ORIGIN_REASON_CODES = (
    "SOURCE_FRAGMENT_UNREVIEWED", "CONFLICT_NAME_PARSE", "CONFLICT_CANONICAL_VALUE",
    "CONFLICT_EDUCATION_IDENTITY", "CONFLICT_TRAINING_IDENTITY", "RUN_EXECUTION_ERROR",
    "RUN_ACCEPTANCE_PAUSED", "RUN_PARTICIPANT_ERROR",
)
PPR_PROJECTION_OUTBOX_JOB_KINDS = ("TARGETED_RECALCULATE", "TARGETED_INVALIDATE", "POLICY_BATCH_INVALIDATE")
PPR_PROJECTION_OUTBOX_STATES = ("PENDING", "PROCESSING", "RETRY", "COMPLETED", "DEAD")
PPR_PROJECTION_OUTBOX_ERROR_CODES = ("PROJECTOR_TRANSIENT", "PROJECTOR_CONFLICT", "PROJECTOR_INTERNAL", "LOCK_TIMEOUT", "FINGERPRINT_MISMATCH")


class PprSectionManualCorrectionEvent(Base):
    __tablename__ = "ppr_section_manual_correction_events"
    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False, default=PPR_CORRECTION_EVENT_TYPE)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, unique=True)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("persons.person_id"), nullable=False)
    employee_context_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("employees.employee_id"))
    universe_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ppr_migration_status_universes.universe_id"), nullable=False)
    cohort_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ppr_stage0_cohort_runs.stage0_cohort_run_id"), nullable=False)
    section_code: Mapped[str] = mapped_column(Text, nullable=False)
    origin_status: Mapped[str] = mapped_column(Text, nullable=False)
    origin_reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    stage_run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ppr_stage_runs.stage_run_id"))
    stage1_run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ppr_stage1_general_runs.stage1_run_id"))
    stage_participant_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ppr_stage_run_participants.stage_run_participant_id"))
    stage1_participant_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ppr_stage1_general_participants.stage1_participant_id"))
    pmf_run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("personnel_migration_runs.run_id"))
    pmf_item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("personnel_migration_items.item_id"))
    evidence_event_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("personnel_record_events.event_id"))
    before_source_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    before_target_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    before_binding_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    after_source_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    after_target_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    after_binding_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    optimistic_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PprMigrationProjectionOutbox(Base):
    __tablename__ = "ppr_migration_projection_outbox"
    outbox_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ppr_section_manual_correction_events.event_id"), nullable=False, unique=True)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, unique=True)
    universe_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ppr_migration_status_universes.universe_id"), nullable=False)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("persons.person_id"), nullable=False)
    section_code: Mapped[str] = mapped_column(Text, nullable=False)
    job_kind: Mapped[str] = mapped_column(Text, nullable=False)
    state_code: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[str | None] = mapped_column(Text)
    last_error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
