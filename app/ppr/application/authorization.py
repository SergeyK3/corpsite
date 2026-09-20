"""Authorization port for PPR application write path (R5)."""
from __future__ import annotations

from typing import Any, Protocol

from app.ppr.domain.errors import PprAuthorizationDeniedError
from app.security.directory_scope import is_privileged
from app.security.personnel_admin_guard import evaluate_personnel_admin_access


class AuthorizationPort(Protocol):
    def authorize_mutation(
        self,
        *,
        actor_id: str,
        operation_code: str,
        person_id: int,
        employee_context_id: int | None = None,
        section_code: str | None = None,
    ) -> None:
        ...


def check_hr_import_admin_access(user_ctx: dict[str, Any]) -> bool:
    """HR import write access — same semantics as PMF router, no HTTP layer."""
    if is_privileged(user_ctx):
        return True
    user_id = user_ctx.get("user_id") or user_ctx.get("id")
    if user_id is None:
        return False
    ctx = dict(user_ctx)
    if "user_id" not in ctx and "id" in ctx:
        ctx["user_id"] = ctx["id"]
    return evaluate_personnel_admin_access(ctx)


class AllowAllAuthorizationPort:
    """Test double — permits all mutations."""

    def authorize_mutation(
        self,
        *,
        actor_id: str,
        operation_code: str,
        person_id: int,
        employee_context_id: int | None = None,
        section_code: str | None = None,
    ) -> None:
        del actor_id, operation_code, person_id, employee_context_id, section_code


class HrImportAdminAuthorizationAdapter:
    """Production adapter — maps RBAC check to PprAuthorizationDeniedError."""

    def __init__(self, user_ctx: dict[str, Any]) -> None:
        self._user_ctx = user_ctx

    def authorize_mutation(
        self,
        *,
        actor_id: str,
        operation_code: str,
        person_id: int,
        employee_context_id: int | None = None,
        section_code: str | None = None,
    ) -> None:
        del operation_code, person_id, employee_context_id, section_code
        if not check_hr_import_admin_access(self._user_ctx):
            raise PprAuthorizationDeniedError("HR import admin access required")
        resolved_actor = str(self._user_ctx.get("user_id") or self._user_ctx.get("id") or "")
        if actor_id and resolved_actor and actor_id != resolved_actor:
            raise PprAuthorizationDeniedError("actor_id does not match authenticated user")


class PersonnelCardEditAuthorizationAdapter:
    """Production port for the dedicated Personnel Card correction permission."""

    def __init__(self, user_ctx: dict[str, Any]) -> None:
        self._user_ctx = user_ctx

    def authorize_mutation(self, *, actor_id: str, operation_code: str, person_id: int,
                           employee_context_id: int | None = None, section_code: str | None = None) -> None:
        del operation_code, person_id, employee_context_id, section_code
        from app.security.personnel_card_edit import has_personnel_card_edit
        if not has_personnel_card_edit(self._user_ctx):
            raise PprAuthorizationDeniedError("Permission required: PERSONNEL_CARD_EDIT")
        resolved_actor = str(self._user_ctx.get("user_id") or self._user_ctx.get("id") or "")
        if not resolved_actor or actor_id != resolved_actor:
            raise PprAuthorizationDeniedError("actor_id does not match authenticated user")


class SelfPersonalCardAuthorizationAdapter:
    """Allows a mutation only for the Person already resolved from this user."""

    def __init__(self, user_ctx: dict[str, Any], *, person_id: int) -> None:
        self._user_ctx = user_ctx
        self._person_id = int(person_id)

    def authorize_mutation(self, *, actor_id: str, operation_code: str, person_id: int,
                           employee_context_id: int | None = None, section_code: str | None = None) -> None:
        del operation_code, employee_context_id, section_code
        resolved_actor = str(self._user_ctx.get("user_id") or self._user_ctx.get("id") or "")
        if not resolved_actor or actor_id != resolved_actor or int(person_id) != self._person_id:
            raise PprAuthorizationDeniedError("Self personal-card subject mismatch")
