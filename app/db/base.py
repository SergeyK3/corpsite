"""SQLAlchemy declarative base for Corpsite ORM models."""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata registry for SQLAlchemy models."""
