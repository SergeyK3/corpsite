"""Application-capable Unit of Work (R5 — envelope, events, sections, idempotency)."""
from __future__ import annotations

from types import TracebackType

from sqlalchemy.engine import Connection, Engine

from app.db.engine import engine as default_engine
from app.ppr.domain.command_idempotency_repositories import CommandIdempotencyRepository
from app.ppr.domain.event_repositories import PprEventRepository
from app.ppr.domain.repositories import PprRepository
from app.ppr.domain.section_mutation_context import SectionMutationContext
from app.ppr.domain.section_repositories import SectionReadRepository
from app.ppr.infrastructure.command_idempotency_repository import SqlAlchemyCommandIdempotencyRepository
from app.ppr.infrastructure.identity_repository import SqlAlchemyIdentityRepository
from app.ppr.infrastructure.person_repository import SqlAlchemyPersonRepository
from app.ppr.infrastructure.ppr_event_repository import SqlAlchemyPprEventRepository
from app.ppr.infrastructure.ppr_repository import SqlAlchemyPprRepository
from app.ppr.infrastructure.section_repository import (
    SqlAlchemySectionMutationRepository,
    SqlAlchemySectionReadRepository,
)
from app.ppr.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


class PprApplicationUnitOfWork(SqlAlchemyUnitOfWork):
    """R5 UoW: one Connection, one transaction, all write collaborators."""

    def __init__(
        self,
        *,
        conn: Connection | None = None,
        db_engine: Engine | None = None,
    ) -> None:
        super().__init__(conn=conn, db_engine=db_engine)
        self._envelopes: PprRepository | None = None
        self._events: PprEventRepository | None = None
        self._commands: CommandIdempotencyRepository | None = None
        self._identity: SqlAlchemyIdentityRepository | None = None
        self._persons: SqlAlchemyPersonRepository | None = None
        self._closed = False
        self._participating = False

    def bind_participating(self, conn: Connection) -> PprApplicationUnitOfWork:
        """Join caller-owned transaction — commit/rollback are no-ops."""
        if self._closed:
            raise RuntimeError("UnitOfWork is closed and cannot be reused")
        self._participating = True
        self._external_conn = conn
        self._conn = conn
        self._transaction = None
        self._bind_repositories(conn)
        return self

    def release_participating(self) -> None:
        """Drop repository handles without touching caller transaction."""
        self._invalidate_after_transaction()
        self._participating = False
        self._conn = None
        self._external_conn = None

    def _bind_repositories(self, conn: Connection) -> None:
        self._sections_read = SqlAlchemySectionReadRepository(conn)
        self._mutation_repo = SqlAlchemySectionMutationRepository(conn)
        self._mutation_ctx = SectionMutationContext(self._mutation_repo)
        self._envelopes = SqlAlchemyPprRepository(conn)
        self._events = SqlAlchemyPprEventRepository(conn)
        self._commands = SqlAlchemyCommandIdempotencyRepository(conn)
        self._identity = SqlAlchemyIdentityRepository(conn)
        self._persons = SqlAlchemyPersonRepository(conn)

    @property
    def envelopes(self) -> PprRepository:
        if self._envelopes is None:
            raise RuntimeError("UnitOfWork is not started")
        return self._envelopes

    @property
    def events(self) -> PprEventRepository:
        if self._events is None:
            raise RuntimeError("UnitOfWork is not started")
        return self._events

    @property
    def command_idempotency(self) -> CommandIdempotencyRepository:
        if self._commands is None:
            raise RuntimeError("UnitOfWork is not started")
        return self._commands

    @property
    def identity(self) -> SqlAlchemyIdentityRepository:
        if self._identity is None:
            raise RuntimeError("UnitOfWork is not started")
        return self._identity

    @property
    def persons(self) -> SqlAlchemyPersonRepository:
        if self._persons is None:
            raise RuntimeError("UnitOfWork is not started")
        return self._persons

    def begin(self) -> PprApplicationUnitOfWork:
        if self._participating:
            if self._conn is not None:
                return self
            raise RuntimeError("Participating UoW must be bound via bind_participating(conn)")
        if self._closed:
            raise RuntimeError("UnitOfWork is closed and cannot be reused")
        super().begin()
        self._bind_repositories(self.connection)
        return self

    def commit(self) -> None:
        if self._participating:
            return
        super().commit()
        self._invalidate_after_transaction()

    def rollback(self) -> None:
        if self._participating:
            return
        super().rollback()
        self._invalidate_after_transaction()

    def _invalidate_after_transaction(self) -> None:
        self._envelopes = None
        self._events = None
        self._commands = None
        self._identity = None
        self._persons = None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._participating:
            self.release_participating()
            return
        super().__exit__(exc_type, exc, tb)
        self._invalidate_after_transaction()
        self._closed = True
