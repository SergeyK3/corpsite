"""Personnel Application ORM model (ADR-057)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.personnel_applications.domain.status import (
    APPLICATION_SOURCE_PAPER,
    APPLICATION_STATUS_REGISTERED,
    REGISTRATION_INITIAL_STATUS,
    VACANCY_CHECK_PENDING,
)

__all__ = ["PersonnelApplication"]


class PersonnelApplication(Base):
    __tablename__ = "personnel_applications"

    application_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    person_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("persons.person_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{REGISTRATION_INITIAL_STATUS}'"),
    )
    application_received_at: Mapped[date] = mapped_column(Date, nullable=False)
    application_source: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{APPLICATION_SOURCE_PAPER}'"),
    )
    vacancy_check_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{VACANCY_CHECK_PENDING}'"),
    )
    vacancy_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vacancy_checked_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=True,
    )
    intended_org_group_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    intended_org_unit_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    intended_position_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    intended_employment_rate: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    intended_vacancy_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_mobile_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    director_resolution_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    director_resolution_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    director_resolution_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=True,
    )
    director_resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    personnel_order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("personnel_orders.order_id", ondelete="RESTRICT"),
        nullable=True,
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    registered_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    hr_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
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
