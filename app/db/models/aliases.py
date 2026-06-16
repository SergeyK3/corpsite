"""Org unit and position alias ORM models (ADR-038 Phase 2A)."""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrgUnitAlias(Base):
    """Normalized alias for org unit name matching during HR import."""

    __tablename__ = "org_unit_aliases"
    __table_args__ = (
        UniqueConstraint("normalized_alias", name="uq_org_unit_aliases_normalized"),
        Index("ix_org_unit_aliases_org_unit", "org_unit_id"),
    )

    alias_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_unit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("org_units.unit_id", ondelete="CASCADE"),
        nullable=False,
    )
    alias_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_alias: Mapped[str] = mapped_column(Text, nullable=False)


class PositionAlias(Base):
    """Normalized alias for position name matching during HR import."""

    __tablename__ = "position_aliases"
    __table_args__ = (
        UniqueConstraint("normalized_alias", name="uq_position_aliases_normalized"),
        Index("ix_position_aliases_position", "position_id"),
    )

    alias_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    position_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("positions.position_id", ondelete="CASCADE"),
        nullable=False,
    )
    alias_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_alias: Mapped[str] = mapped_column(Text, nullable=False)
