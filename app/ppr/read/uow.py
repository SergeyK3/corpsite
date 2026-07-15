"""Read-only Unit of Work for PPR query layer (R6 — no mutations)."""
from __future__ import annotations

from types import TracebackType

from sqlalchemy.engine import Connection, Engine

from app.db.engine import engine as default_engine
from app.ppr.domain.event_repositories import PprEventRepository
from app.ppr.domain.repositories import PprRepository
from app.ppr.domain.section_repositories import SectionReadRepository
from app.ppr.infrastructure.identity_repository import SqlAlchemyIdentityRepository
from app.ppr.infrastructure.person_repository import SqlAlchemyPersonRepository
from app.ppr.infrastructure.ppr_event_repository import SqlAlchemyPprEventRepository
from app.ppr.infrastructure.ppr_repository import SqlAlchemyPprRepository
from app.ppr.infrastructure.section_repository import SqlAlchemySectionReadRepository


class PprReadUnitOfWork:
    """Exposes read repositories only — no section mutations, no command idempotency."""

    def __init__(
        self,
        *,
        conn: Connection | None = None,
        db_engine: Engine | None = None,
    ) -> None:
        self._engine = db_engine or default_engine
        self._external_conn = conn
        self._conn: Connection | None = None
        self._connection_ctx = None
        self._identity: SqlAlchemyIdentityRepository | None = None
        self._persons: SqlAlchemyPersonRepository | None = None
        self._sections: SectionReadRepository | None = None
        self._envelopes: PprRepository | None = None
        self._events: PprEventRepository | None = None

    @property
    def identity(self) -> SqlAlchemyIdentityRepository:
        if self._identity is None:
            raise RuntimeError("PprReadUnitOfWork is not started")
        return self._identity

    @property
    def persons(self) -> SqlAlchemyPersonRepository:
        if self._persons is None:
            raise RuntimeError("PprReadUnitOfWork is not started")
        return self._persons

    @property
    def sections(self) -> SectionReadRepository:
        if self._sections is None:
            raise RuntimeError("PprReadUnitOfWork is not started")
        return self._sections

    @property
    def envelopes(self) -> PprRepository:
        if self._envelopes is None:
            raise RuntimeError("PprReadUnitOfWork is not started")
        return self._envelopes

    @property
    def events(self) -> PprEventRepository:
        if self._events is None:
            raise RuntimeError("PprReadUnitOfWork is not started")
        return self._events

    @property
    def connection(self) -> Connection:
        if self._conn is None:
            raise RuntimeError("PprReadUnitOfWork is not started")
        return self._conn

    def _bind_repositories(self, conn: Connection) -> None:
        self._identity = SqlAlchemyIdentityRepository(conn)
        self._persons = SqlAlchemyPersonRepository(conn)
        self._sections = SqlAlchemySectionReadRepository(conn)
        self._envelopes = SqlAlchemyPprRepository(conn)
        self._events = SqlAlchemyPprEventRepository(conn)

    def __enter__(self) -> PprReadUnitOfWork:
        if self._conn is not None:
            return self
        if self._external_conn is not None:
            self._conn = self._external_conn
        else:
            self._connection_ctx = self._engine.connect()
            self._conn = self._connection_ctx.__enter__()
        self._bind_repositories(self._conn)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._identity = None
        self._persons = None
        self._sections = None
        self._envelopes = None
        self._events = None
        if self._connection_ctx is not None:
            self._connection_ctx.__exit__(exc_type, exc, tb)
            self._connection_ctx = None
        self._conn = None
