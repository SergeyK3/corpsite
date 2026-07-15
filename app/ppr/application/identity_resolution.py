"""Identity resolution for application commands (R2)."""
from __future__ import annotations

from app.ppr.domain.errors import PprIdentityInputMismatchError, PprPersonNotFoundError
from app.ppr.domain.identity_repositories import IdentityRepository


def resolve_canonical_person_id(
    identity: IdentityRepository,
    *,
    person_id: int | None,
    employee_id: int | None,
) -> int:
    if person_id is None and employee_id is None:
        raise PprIdentityInputMismatchError("person_id or employee_id is required")

    resolved_from_person: int | None = None
    resolved_from_employee: int | None = None

    if person_id is not None:
        if person_id <= 0:
            raise PprIdentityInputMismatchError("person_id must be positive")
        resolved_from_person = identity.resolve_survivor(person_id)

    if employee_id is not None:
        if employee_id <= 0:
            raise PprIdentityInputMismatchError("employee_id must be positive")
        resolution = identity.resolve_employee_id(employee_id)
        resolved_from_employee = resolution.resolved_person_id

    if resolved_from_person is not None and resolved_from_employee is not None:
        if resolved_from_person != resolved_from_employee:
            raise PprIdentityInputMismatchError(
                "person_id and employee_id resolve to different canonical persons"
            )
        return resolved_from_person

    result = resolved_from_person if resolved_from_person is not None else resolved_from_employee
    if result is None:
        raise PprPersonNotFoundError("Unable to resolve canonical person_id")
    return result
