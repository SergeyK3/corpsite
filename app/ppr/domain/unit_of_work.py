"""UnitOfWork contract (R4 transaction primitives for R5 orchestration)."""
from __future__ import annotations

from typing import Protocol

from sqlalchemy.engine import Connection

from app.ppr.domain.section_mutation_context import SectionMutationContext
from app.ppr.domain.section_repositories import SectionReadRepository


class UnitOfWork(Protocol):
    """Owns DB transaction; read and mutation section access are separated."""

    @property
    def sections(self) -> SectionReadRepository:
        """Read-only section adapter bound to this transaction."""
        ...

    @property
    def connection(self) -> Connection:
        """Open DB connection for the current transaction (no commit by callers)."""
        ...

    def section_mutations(self) -> SectionMutationContext:
        """Handler-scoped write access; not available on the read repository."""
        ...

    def commit(self) -> None:
        """Commit the open transaction."""
        ...

    def rollback(self) -> None:
        """Rollback the open transaction."""
        ...
