"""MRD domain error → HTTP mapping (WP-MRD-004)."""
from __future__ import annotations

from fastapi import HTTPException

from app.mrd.domain.errors import (
    ActiveMrdAmbiguousError,
    ActiveMrdMissingError,
    DifferenceOriginError,
    ForkForbiddenError,
    MrdCommandConflictError,
    MrdDomainError,
    MrdInvariantViolationError,
    MrdMutationForbiddenError,
    MrdNotFoundError,
    MrdOptimisticConcurrencyConflictError,
    MrdPeriodExistsError,
    MrdPeriodWindowError,
    MrdVersionDuplicateError,
)


def mrd_not_found_http404(exc: MrdNotFoundError | ActiveMrdMissingError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def mrd_conflict_http409(exc: Exception) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


def mrd_validation_http422(exc: Exception) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


def map_mrd_error(exc: Exception) -> HTTPException | None:
    if isinstance(exc, (MrdNotFoundError, ActiveMrdMissingError)):
        return mrd_not_found_http404(exc)
    if isinstance(
        exc,
        (
            MrdCommandConflictError,
            MrdOptimisticConcurrencyConflictError,
            MrdPeriodExistsError,
            MrdVersionDuplicateError,
            ActiveMrdAmbiguousError,
            ForkForbiddenError,
            MrdMutationForbiddenError,
            MrdInvariantViolationError,
        ),
    ):
        return mrd_conflict_http409(exc)
    if isinstance(exc, (DifferenceOriginError, MrdPeriodWindowError, MrdDomainError)):
        return mrd_validation_http422(exc)
    return None
