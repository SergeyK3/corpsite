"""Employee identity ORM model (ADR-038 Phase 2A)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

IDENTITY_TYPE_IIN = "IIN"


class EmployeeIdentity(Base):
    """Canonical store for employee identifiers (IIN and future types)."""

    __tablename__ = "employee_identities"
    __table_args__ = (
        Index(
            "uq_employee_identities_iin_active",
            "identity_value",
            unique=True,
            postgresql_where=text("identity_type = 'IIN' AND valid_to IS NULL"),
        ),
        Index("ix_employee_identities_employee", "employee_id"),
        Index(
            "ix_employee_identities_type_value",
            "identity_type",
            "identity_value",
        ),
    )

    identity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("employees.employee_id", ondelete="CASCADE"),
        nullable=False,
    )
    identity_type: Mapped[str] = mapped_column(Text, nullable=False)
    identity_value: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
