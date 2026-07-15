"""SQLAlchemy UnitOfWork (R4 transaction ownership primitives)."""
from __future__ import annotations

from types import TracebackType

from sqlalchemy.engine import Connection, Engine

from app.db.engine import engine as default_engine
from app.ppr.domain.section_mutation_context import SectionMutationContext
from app.ppr.domain.section_repositories import SectionReadRepository
from app.ppr.infrastructure.section_repository import (
    SqlAlchemySectionMutationRepository,
    SqlAlchemySectionReadRepository,
)


class SqlAlchemyUnitOfWork:
    """Owns one Connection transaction; exposes read-only sections + mutation context."""

    def __init__(
        self,
        *,
        conn: Connection | None = None,
        db_engine: Engine | None = None,
    ) -> None:
        self._engine = db_engine or default_engine
        self._external_conn = conn
        self._conn: Connection | None = None
        self._transaction = None
        self._connection_ctx = None
        self._sections_read: SectionReadRepository | None = None
        self._mutation_repo: SqlAlchemySectionMutationRepository | None = None
        self._mutation_ctx: SectionMutationContext | None = None
        self._committed = False

    @property
    def sections(self) -> SectionReadRepository:
        if self._sections_read is None:
            raise RuntimeError("UnitOfWork is not started — use as context manager or call begin()")
        return self._sections_read

    def section_mutations(self) -> SectionMutationContext:
        if self._mutation_ctx is None:
            raise RuntimeError("UnitOfWork is not started — use as context manager or call begin()")
        return self._mutation_ctx

    @property
    def connection(self) -> Connection:
        if self._conn is None:
            raise RuntimeError("UnitOfWork is not started")
        return self._conn

    def begin(self) -> SqlAlchemyUnitOfWork:
        if self._conn is not None:
            return self
        if self._external_conn is not None:
            self._conn = self._external_conn
        else:
            self._connection_ctx = self._engine.connect()
            self._conn = self._connection_ctx.__enter__()
        self._transaction = self._conn.begin()
        self._sections_read = SqlAlchemySectionReadRepository(self._conn)
        self._mutation_repo = SqlAlchemySectionMutationRepository(self._conn)
        self._mutation_ctx = SectionMutationContext(self._mutation_repo)
        self._committed = False
        return self

    def commit(self) -> None:
        if self._transaction is None:
            raise RuntimeError("No open transaction to commit")
        self._transaction.commit()
        self._transaction = None
        self._committed = True

    def rollback(self) -> None:
        if self._transaction is not None:
            self._transaction.rollback()
            self._transaction = None
        self._committed = False

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        return self.begin()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.rollback()
        elif not self._committed and self._transaction is not None:
            self.rollback()

        if self._connection_ctx is not None:
            self._connection_ctx.__exit__(exc_type, exc, tb)
            self._connection_ctx = None
        self._conn = None
        self._sections_read = None
        self._mutation_repo = None
        self._mutation_ctx = None
