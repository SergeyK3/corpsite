"""Participating Unit of Work helpers (R5 — join caller-owned transaction)."""
from __future__ import annotations

from sqlalchemy.engine import Connection

from app.ppr.infrastructure.application_unit_of_work import PprApplicationUnitOfWork


def bind_participating_uow(conn: Connection) -> PprApplicationUnitOfWork:
    """Create UoW bound to an open caller transaction (no nested begin/commit)."""
    uow = PprApplicationUnitOfWork(conn=conn)
    uow.bind_participating(conn)
    return uow
