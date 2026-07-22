"""PPR domain error → HTTP mapping for query and command APIs."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.ppr.domain.errors import (
    PprApplicationValidationError,
    PprAuthorizationDeniedError,
    PprCommandIdConflictError,
    PprCommandInProgressError,
    PprEmployeeNotFoundError,
    PprEmployeePersonLinkMissingError,
    PprIdentityInputMismatchError,
    PprIdentityResolutionError,
    PprLifecycleTransitionError,
    PprNotMaterializedError,
    PprOptimisticConcurrencyConflictError,
    PprPersonNotFoundError,
    PprReadLegacyAdapterError,
    PprReadPathConfigError,
    SectionOptimisticConcurrencyConflictError,
    SectionRecordNotFoundError,
    SectionValidationError,
)

MILITARY_ONE_ACTIVE_PER_PERSON_CONSTRAINT = "uq_person_military_service_one_active_per_person"
MILITARY_ACTIVE_RECORD_ALREADY_EXISTS = (
    "У сотрудника уже есть действующая запись воинского учёта. "
    "Измените существующую запись через замену."
)


def _integrity_error_pgcode(exc: IntegrityError) -> str | None:
    orig = getattr(exc, "orig", None)
    if orig is None:
        return None
    pgcode = getattr(orig, "pgcode", None)
    return str(pgcode) if pgcode is not None else None


def _integrity_error_constraint_name(exc: IntegrityError) -> str | None:
    orig = getattr(exc, "orig", None)
    if orig is None:
        return None
    diag = getattr(orig, "diag", None)
    if diag is None:
        return None
    constraint_name = getattr(diag, "constraint_name", None)
    return str(constraint_name) if constraint_name is not None else None


def _is_military_second_active_conflict(exc: IntegrityError) -> bool:
    return (
        _integrity_error_pgcode(exc) == "23505"
        and _integrity_error_constraint_name(exc) == MILITARY_ONE_ACTIVE_PER_PERSON_CONSTRAINT
    )


def ppr_not_found_http404(exc: LookupError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def ppr_forbidden_http403(exc: PprAuthorizationDeniedError) -> HTTPException:
    return HTTPException(status_code=403, detail=str(exc))


def ppr_conflict_http409(exc: Exception) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


def ppr_validation_http422(exc: Exception) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


def ppr_config_http503(exc: PprReadPathConfigError | PprReadLegacyAdapterError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


def map_ppr_query_error(exc: Exception) -> HTTPException | None:
    if isinstance(exc, PprAuthorizationDeniedError):
        return ppr_forbidden_http403(exc)
    if isinstance(exc, (PprPersonNotFoundError, PprEmployeeNotFoundError)):
        return ppr_not_found_http404(exc)
    if isinstance(exc, PprEmployeePersonLinkMissingError):
        return ppr_conflict_http409(exc)
    if isinstance(exc, PprIdentityInputMismatchError):
        return ppr_validation_http422(exc)
    if isinstance(exc, PprIdentityResolutionError):
        return ppr_conflict_http409(exc)
    if isinstance(exc, (PprReadPathConfigError, PprReadLegacyAdapterError)):
        return ppr_config_http503(exc)
    return None


def map_ppr_mutation_error(exc: Exception) -> HTTPException | None:
    mapped = map_ppr_query_error(exc)
    if mapped is not None:
        return mapped
    if isinstance(exc, SectionValidationError):
        return ppr_validation_http422(exc)
    if isinstance(exc, SectionRecordNotFoundError):
        return ppr_not_found_http404(exc)
    if isinstance(
        exc,
        (
            SectionOptimisticConcurrencyConflictError,
            PprOptimisticConcurrencyConflictError,
            PprNotMaterializedError,
            PprCommandIdConflictError,
            PprCommandInProgressError,
            PprLifecycleTransitionError,
        ),
    ):
        return ppr_conflict_http409(exc)
    if isinstance(exc, PprApplicationValidationError):
        return ppr_validation_http422(exc)
    if isinstance(exc, IntegrityError) and _is_military_second_active_conflict(exc):
        return HTTPException(status_code=409, detail=MILITARY_ACTIVE_RECORD_ALREADY_EXISTS)
    return None
