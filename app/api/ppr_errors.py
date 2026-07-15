"""PPR domain error → HTTP mapping for query API (R7)."""
from __future__ import annotations

from fastapi import HTTPException

from app.ppr.domain.errors import (
    PprAuthorizationDeniedError,
    PprEmployeeNotFoundError,
    PprEmployeePersonLinkMissingError,
    PprIdentityInputMismatchError,
    PprIdentityResolutionError,
    PprPersonNotFoundError,
    PprReadLegacyAdapterError,
    PprReadPathConfigError,
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
