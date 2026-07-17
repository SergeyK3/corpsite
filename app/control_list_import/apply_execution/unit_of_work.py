"""Apply execution unit of work (WP-CL-012)."""
from __future__ import annotations

from sqlalchemy.engine import Connection

from app.control_list_import.infrastructure.apply_execution_repository import (
    SqlAlchemyApplyExecutionRepository,
)


class SqlAlchemyApplyExecutionUnitOfWork:
    """One journal transaction boundary per commit."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn
        self._repository = SqlAlchemyApplyExecutionRepository(conn)

    @property
    def repository(self) -> SqlAlchemyApplyExecutionRepository:
        return self._repository

    def commit(self) -> None:
        if self._conn.in_transaction():
            self._conn.commit()

    def rollback(self) -> None:
        if self._conn.in_transaction():
            self._conn.rollback()
