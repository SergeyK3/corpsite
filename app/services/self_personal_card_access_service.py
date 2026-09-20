"""Server-side subject resolution for an employee's own personal card.

This module deliberately does not import personnel RBAC/visibility helpers.
The only subject is derived from the authenticated user's persisted
``users.employee_id`` link, then from that Employee's ``person_id`` link.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.engine import engine as default_engine
from app.ppr.domain.errors import (
    PprEmployeeNotFoundError,
    PprEmployeePersonLinkMissingError,
    PprIdentityResolutionError,
    PprPersonNotFoundError,
)
from app.ppr.read.models import PprCompositeReadModel
from app.ppr.read.query_service import PprQueryApplicationService


SelfCardStatus = Literal[
    "READY",
    "NO_EMPLOYEE_LINK",
    "PERSON_NOT_LINKED",
    "IDENTITY_AMBIGUOUS",
]


@dataclass(frozen=True, slots=True)
class SelfPersonalCardResolution:
    """Outcome of resolving the authenticated user to one canonical PPR card."""

    status: SelfCardStatus
    composite: PprCompositeReadModel | None = None


class SelfPersonalCardAccessService:
    """Resolve only the caller's Person; never accept a client subject identifier."""

    def __init__(
        self,
        *,
        db_engine: Engine | None = None,
        query_service: PprQueryApplicationService | None = None,
    ) -> None:
        self._engine = db_engine or default_engine
        self._query_service = query_service or PprQueryApplicationService()

    def resolve_for_user(self, user_ctx: dict[str, Any]) -> SelfPersonalCardResolution:
        """Return a controlled state instead of leaking linkage details.

        ``get_current_user`` already establishes authentication and active-user
        status. The active-user predicate is intentionally repeated here so
        direct/internal callers cannot bypass this invariant.
        """
        user_id = int(user_ctx["user_id"])
        with self._engine.connect() as conn:
            link = conn.execute(
                text(
                    """
                    SELECT e.employee_id, e.person_id
                    FROM public.users u
                    LEFT JOIN public.employees e ON e.employee_id = u.employee_id
                    WHERE u.user_id = :user_id
                      AND COALESCE(u.is_active, FALSE) IS TRUE
                      AND COALESCE(e.is_active, FALSE) IS TRUE
                    """
                ),
                {"user_id": user_id},
            ).mappings().one_or_none()

        if link is None or link.get("employee_id") is None:
            return SelfPersonalCardResolution(status="NO_EMPLOYEE_LINK")
        if link.get("person_id") is None:
            return SelfPersonalCardResolution(status="PERSON_NOT_LINKED")

        employee_id = int(link["employee_id"])
        direct_person_id = int(link["person_id"])
        try:
            composite = self._query_service.load_by_employee_id(
                employee_id,
                include_events=False,
            )
        except (
            PprEmployeeNotFoundError,
            PprEmployeePersonLinkMissingError,
            PprPersonNotFoundError,
            PprIdentityResolutionError,
        ):
            # A broken/merged/cyclic link is deliberately indistinguishable to
            # the browser from other identity ambiguity.
            return SelfPersonalCardResolution(status="IDENTITY_AMBIGUOUS")

        with self._engine.connect() as conn:
            active_employee_count = int(
                conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM public.employees
                        WHERE COALESCE(is_active, FALSE) IS TRUE
                          AND (person_id = :direct_person_id OR person_id = :resolved_person_id)
                        """
                    ),
                    {
                        "direct_person_id": direct_person_id,
                        "resolved_person_id": int(composite.person_id),
                    },
                ).scalar_one()
            )
        if active_employee_count != 1:
            return SelfPersonalCardResolution(status="IDENTITY_AMBIGUOUS")

        return SelfPersonalCardResolution(status="READY", composite=composite)
