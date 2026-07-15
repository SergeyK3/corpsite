"""PPR aggregate envelope ORM model (personnel_record_metadata)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.ppr.domain.models import (
    HR_RELATIONSHIP_UNKNOWN,
    PPR_ENVELOPE_INITIAL_HR_RELATIONSHIP_CONTEXT,
    PPR_ENVELOPE_INITIAL_LIFECYCLE_STATE,
    PPR_ENVELOPE_INITIAL_VERSION,
    PPR_LIFECYCLE_CREATED,
    PPR_LIFECYCLE_STATES,
    HR_RELATIONSHIP_CONTEXTS,
)

__all__ = [
    "HR_RELATIONSHIP_CONTEXTS",
    "HR_RELATIONSHIP_UNKNOWN",
    "PPR_ENVELOPE_INITIAL_HR_RELATIONSHIP_CONTEXT",
    "PPR_ENVELOPE_INITIAL_LIFECYCLE_STATE",
    "PPR_ENVELOPE_INITIAL_VERSION",
    "PPR_LIFECYCLE_CREATED",
    "PPR_LIFECYCLE_STATES",
    "PersonnelRecordMetadata",
]


class PersonnelRecordMetadata(Base):
    """Minimal PPR aggregate envelope (ADR-054, WP-PR-010)."""

    __tablename__ = "personnel_record_metadata"

    person_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("persons.person_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    ppr_lifecycle_state: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{PPR_ENVELOPE_INITIAL_LIFECYCLE_STATE}'"),
    )
    hr_relationship_context: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{PPR_ENVELOPE_INITIAL_HR_RELATIONSHIP_CONTEXT}'"),
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text(str(PPR_ENVELOPE_INITIAL_VERSION)),
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
