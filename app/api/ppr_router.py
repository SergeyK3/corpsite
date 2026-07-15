"""PPR composite read REST API (R7 — read-only)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path

from app.api.ppr_errors import map_ppr_query_error
from app.api.ppr_mappers import composite_to_response, summary_to_response
from app.api.ppr_schemas import PprCompositeReadResponse, PprCompositeSummaryResponse
from app.auth import get_current_user
from app.directory.common import as_http500
from app.ppr.application.config import assert_ppr_read_path_activation_allowed
from app.ppr.read.query_service import PprQueryApplicationService
from app.services.ppr_query_access_service import (
    assert_ppr_read_allowed_for_employee,
    assert_ppr_read_allowed_for_person,
    include_sensitive_identity_fields,
)

router = APIRouter(prefix="/api/ppr", tags=["ppr"])

_query_service = PprQueryApplicationService()


@router.get("/persons/{person_id}", response_model=PprCompositeReadResponse)
def get_ppr_composite_by_person(
    person_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCompositeReadResponse:
    """Canonical PPR composite read by person_id (always PPR-native path)."""
    try:
        assert_ppr_read_path_activation_allowed()
        composite = _query_service.load_by_person_id(person_id)
        assert_ppr_read_allowed_for_person(
            user,
            composite.person_id,
            resolved_employee_id=composite.employee_id,
        )
        return composite_to_response(
            composite,
            read_mode="ppr",
            source="ppr_query_api",
            include_sensitive_identity=include_sensitive_identity_fields(user),
        )
    except HTTPException:
        raise
    except Exception as exc:
        mapped = map_ppr_query_error(exc)
        if mapped is not None:
            raise mapped
        raise as_http500(exc)


@router.get("/persons/{person_id}/summary", response_model=PprCompositeSummaryResponse)
def get_ppr_summary_by_person(
    person_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCompositeSummaryResponse:
    """Lightweight PPR summary by person_id."""
    try:
        assert_ppr_read_path_activation_allowed()
        summary = _query_service.load_summary(person_id=person_id)
        assert_ppr_read_allowed_for_person(
            user,
            summary.person_id,
            resolved_employee_id=summary.employee_id,
        )
        return summary_to_response(
            summary,
            read_mode="ppr",
            source="ppr_query_api",
            include_sensitive_identity=include_sensitive_identity_fields(user),
        )
    except HTTPException:
        raise
    except Exception as exc:
        mapped = map_ppr_query_error(exc)
        if mapped is not None:
            raise mapped
        raise as_http500(exc)


@router.get("/employees/{employee_id}", response_model=PprCompositeReadResponse)
def get_ppr_composite_by_employee(
    employee_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCompositeReadResponse:
    """Transitional PPR composite read by employee_id (identity resolution applied)."""
    try:
        assert_ppr_read_path_activation_allowed()
        assert_ppr_read_allowed_for_employee(user, employee_id)
        composite = _query_service.load_by_employee_id(employee_id)
        return composite_to_response(
            composite,
            read_mode="ppr",
            source="ppr_query_api",
            include_sensitive_identity=include_sensitive_identity_fields(user),
        )
    except HTTPException:
        raise
    except Exception as exc:
        mapped = map_ppr_query_error(exc)
        if mapped is not None:
            raise mapped
        raise as_http500(exc)
