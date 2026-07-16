"""PPR composite read REST API (R7 — read-only)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path

from app.api.ppr_errors import map_ppr_query_error
from app.api.ppr_mappers import composite_to_response, summary_to_response
from app.api.ppr_schemas import (
    PprCompositeReadResponse,
    PprCompositeSummaryResponse,
    PprHireDefaultsResponse,
    PprIntendedEmploymentResponse,
    PprIntendedEmploymentUpdateRequest,
)
from app.auth import get_current_user
from app.directory.common import as_http500
from app.ppr.application.config import assert_ppr_read_path_activation_allowed
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE
from app.ppr.read.query_service import PprQueryApplicationService
from app.services.ppr_candidate_service import load_hire_defaults, save_intended_employment
from app.services.ppr_query_access_service import (
    assert_ppr_read_allowed_for_employee,
    assert_ppr_read_allowed_for_person,
    include_sensitive_identity_fields,
    require_ppr_write_for_person,
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


@router.get("/persons/{person_id}/hire-defaults", response_model=PprHireDefaultsResponse)
def get_ppr_hire_defaults_by_person(
    person_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprHireDefaultsResponse:
    """Default HIRE order placement from intended employment (read-only)."""
    try:
        assert_ppr_read_path_activation_allowed()
        composite = _query_service.load_by_person_id(person_id)
        assert_ppr_read_allowed_for_person(
            user,
            composite.person_id,
            resolved_employee_id=composite.employee_id,
        )
        from app.db.engine import engine

        if composite.hr_relationship_context != HR_RELATIONSHIP_CANDIDATE:
            raise HTTPException(
                status_code=404,
                detail="Hire defaults are only available for applicants.",
            )
        with engine.begin() as conn:
            defaults = load_hire_defaults(conn, person_id=composite.person_id)
        if defaults is None:
            raise HTTPException(status_code=404, detail="Hire defaults not found.")
        return PprHireDefaultsResponse(**defaults)
    except HTTPException:
        raise
    except Exception as exc:
        mapped = map_ppr_query_error(exc)
        if mapped is not None:
            raise mapped
        raise as_http500(exc)


@router.patch("/persons/{person_id}/intended-employment", response_model=PprIntendedEmploymentResponse)
def patch_ppr_intended_employment(
    body: PprIntendedEmploymentUpdateRequest,
    person_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprIntendedEmploymentResponse:
    """Update intended employment block on PPR envelope (HR only)."""
    try:
        assert_ppr_read_path_activation_allowed()
        require_ppr_write_for_person(user, person_id)
        composite = _query_service.load_by_person_id(person_id)
        if composite.hr_relationship_context != HR_RELATIONSHIP_CANDIDATE:
            raise HTTPException(
                status_code=409,
                detail="Intended employment can only be edited for applicants.",
            )
        from app.db.engine import engine

        with engine.begin() as conn:
            saved = save_intended_employment(
                conn,
                person_id=person_id,
                org_group_id=body.org_group_id,
                org_unit_id=body.org_unit_id,
                position_id=body.position_id,
                employment_rate=body.employment_rate,
            )
        return PprIntendedEmploymentResponse(
            org_group_id=saved.org_group_id,
            org_unit_id=saved.org_unit_id,
            position_id=saved.position_id,
            employment_rate=saved.employment_rate,
            org_group_name=saved.org_group_name,
            org_unit_name=saved.org_unit_name,
            position_name=saved.position_name,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="PPR envelope not found.")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
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
