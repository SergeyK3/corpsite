"""Org-unit allowed positions ORM model (ADR-046 F1)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrgUnitAllowedPosition(Base):
    """Junction: official catalog position is allowed for a specific org unit."""

    __tablename__ = "org_unit_allowed_positions"
    __table_args__ = (
        UniqueConstraint("org_unit_id", "position_id", name="uq_ouap_org_unit_position"),
        Index("ix_ouap_org_unit_id", "org_unit_id"),
        Index("ix_ouap_position_id", "position_id"),
        Index("ix_ouap_org_unit_sort", "org_unit_id", "sort_order", "org_unit_allowed_position_id"),
    )

    org_unit_allowed_position_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    org_unit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("org_units.unit_id", ondelete="RESTRICT"),
        nullable=False,
    )
    position_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("positions.position_id", ondelete="RESTRICT"),
        nullable=False,
    )
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
