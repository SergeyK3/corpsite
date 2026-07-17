"""Director resolution audit ORM (WP-PPR-APPLICANT-002)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

__all__ = ["PersonnelApplicationResolutionAudit"]


class PersonnelApplicationResolutionAudit(Base):
    __tablename__ = "personnel_application_resolution_audit"

    audit_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    application_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("personnel_applications.application_id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    previous_application_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_application_status: Mapped[str] = mapped_column(Text, nullable=False)
    previous_resolution_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_resolution_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
