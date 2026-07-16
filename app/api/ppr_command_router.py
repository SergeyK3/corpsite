"""PPR command REST API — employment biography and military service mutations."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from app.api.ppr_command_schemas import (
    PprCommandMutationResponse,
    PprExternalEmploymentCreateRequest,
    PprExternalEmploymentSupersedeRequest,
    PprExternalEmploymentVoidRequest,
    PprMilitaryServiceCreateRequest,
    PprMilitaryServiceSupersedeRequest,
    PprMilitaryServiceVoidRequest,
)
from app.api.ppr_errors import map_ppr_mutation_error
from app.api.ppr_employment_command_api import (
    create_external_employment_by_employee,
    create_external_employment_by_person,
    supersede_external_employment_by_employee,
    supersede_external_employment_by_person,
    void_external_employment_by_employee,
    void_external_employment_by_person,
)
from app.api.ppr_military_command_api import (
    create_military_service_by_employee,
    create_military_service_by_person,
    supersede_military_service_by_employee,
    supersede_military_service_by_person,
    void_military_service_by_employee,
    void_military_service_by_person,
)
from app.auth import get_current_user
from app.directory.common import as_http500
from app.directory.rbac import require_hr_import_admin_or_403
from app.ppr.application.config import assert_ppr_read_path_activation_allowed
from app.ppr.application.results import RESULT_STATUS_COMMITTED
from app.services.ppr_query_access_service import (
    assert_ppr_read_allowed_for_employee,
    assert_ppr_read_allowed_for_person,
)

router = APIRouter(prefix="/api/ppr", tags=["ppr-commands"])


def _run_mutation(handler, *, response: Response, is_create: bool):
    try:
        assert_ppr_read_path_activation_allowed()
        result = handler()
        if is_create and result.status == RESULT_STATUS_COMMITTED:
            response.status_code = status.HTTP_201_CREATED
        else:
            response.status_code = status.HTTP_200_OK
        return result
    except HTTPException:
        raise
    except Exception as exc:
        mapped = map_ppr_mutation_error(exc)
        if mapped is not None:
            raise mapped
        raise as_http500(exc)


@router.post(
    "/persons/{person_id}/employment-biography/records",
    response_model=PprCommandMutationResponse,
)
def create_employment_biography_by_person(
    body: PprExternalEmploymentCreateRequest,
    response: Response,
    person_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCommandMutationResponse:
    """Create external employment record for a person (canonical route)."""
    require_hr_import_admin_or_403(user)
    assert_ppr_read_allowed_for_person(user, person_id)
    return _run_mutation(
        lambda: create_external_employment_by_person(user, person_id=person_id, body=body),
        response=response,
        is_create=True,
    )


@router.post(
    "/persons/{person_id}/employment-biography/records/{record_id}/void",
    response_model=PprCommandMutationResponse,
)
def void_employment_biography_by_person(
    body: PprExternalEmploymentVoidRequest,
    response: Response,
    person_id: int = Path(..., ge=1),
    record_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCommandMutationResponse:
    """Void an active external employment record for a person."""
    require_hr_import_admin_or_403(user)
    assert_ppr_read_allowed_for_person(user, person_id)
    return _run_mutation(
        lambda: void_external_employment_by_person(
            user,
            person_id=person_id,
            record_id=record_id,
            body=body,
        ),
        response=response,
        is_create=False,
    )


@router.post(
    "/persons/{person_id}/employment-biography/records/{record_id}/supersede",
    response_model=PprCommandMutationResponse,
)
def supersede_employment_biography_by_person(
    body: PprExternalEmploymentSupersedeRequest,
    response: Response,
    person_id: int = Path(..., ge=1),
    record_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCommandMutationResponse:
    """Supersede an active external employment record for a person."""
    require_hr_import_admin_or_403(user)
    assert_ppr_read_allowed_for_person(user, person_id)
    return _run_mutation(
        lambda: supersede_external_employment_by_person(
            user,
            person_id=person_id,
            record_id=record_id,
            body=body,
        ),
        response=response,
        is_create=False,
    )


@router.post(
    "/employees/{employee_id}/employment-biography/records",
    response_model=PprCommandMutationResponse,
)
def create_employment_biography_by_employee(
    body: PprExternalEmploymentCreateRequest,
    response: Response,
    employee_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCommandMutationResponse:
    """Create external employment record via employee_id (identity resolution)."""
    require_hr_import_admin_or_403(user)
    assert_ppr_read_allowed_for_employee(user, employee_id)
    return _run_mutation(
        lambda: create_external_employment_by_employee(user, employee_id=employee_id, body=body),
        response=response,
        is_create=True,
    )


@router.post(
    "/employees/{employee_id}/employment-biography/records/{record_id}/void",
    response_model=PprCommandMutationResponse,
)
def void_employment_biography_by_employee(
    body: PprExternalEmploymentVoidRequest,
    response: Response,
    employee_id: int = Path(..., ge=1),
    record_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCommandMutationResponse:
    """Void an active external employment record via employee_id."""
    require_hr_import_admin_or_403(user)
    assert_ppr_read_allowed_for_employee(user, employee_id)
    return _run_mutation(
        lambda: void_external_employment_by_employee(
            user,
            employee_id=employee_id,
            record_id=record_id,
            body=body,
        ),
        response=response,
        is_create=False,
    )


@router.post(
    "/employees/{employee_id}/employment-biography/records/{record_id}/supersede",
    response_model=PprCommandMutationResponse,
)
def supersede_employment_biography_by_employee(
    body: PprExternalEmploymentSupersedeRequest,
    response: Response,
    employee_id: int = Path(..., ge=1),
    record_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCommandMutationResponse:
    """Supersede an active external employment record via employee_id."""
    require_hr_import_admin_or_403(user)
    assert_ppr_read_allowed_for_employee(user, employee_id)
    return _run_mutation(
        lambda: supersede_external_employment_by_employee(
            user,
            employee_id=employee_id,
            record_id=record_id,
            body=body,
        ),
        response=response,
        is_create=False,
    )


@router.post(
    "/persons/{person_id}/military-service/records",
    response_model=PprCommandMutationResponse,
)
def create_military_service_by_person_route(
    body: PprMilitaryServiceCreateRequest,
    response: Response,
    person_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCommandMutationResponse:
    """Create military service record for a person (canonical route)."""
    require_hr_import_admin_or_403(user)
    assert_ppr_read_allowed_for_person(user, person_id)
    return _run_mutation(
        lambda: create_military_service_by_person(user, person_id=person_id, body=body),
        response=response,
        is_create=True,
    )


@router.post(
    "/persons/{person_id}/military-service/records/{record_id}/void",
    response_model=PprCommandMutationResponse,
)
def void_military_service_by_person_route(
    body: PprMilitaryServiceVoidRequest,
    response: Response,
    person_id: int = Path(..., ge=1),
    record_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCommandMutationResponse:
    """Void an active military service record for a person."""
    require_hr_import_admin_or_403(user)
    assert_ppr_read_allowed_for_person(user, person_id)
    return _run_mutation(
        lambda: void_military_service_by_person(
            user,
            person_id=person_id,
            record_id=record_id,
            body=body,
        ),
        response=response,
        is_create=False,
    )


@router.post(
    "/persons/{person_id}/military-service/records/{record_id}/supersede",
    response_model=PprCommandMutationResponse,
)
def supersede_military_service_by_person_route(
    body: PprMilitaryServiceSupersedeRequest,
    response: Response,
    person_id: int = Path(..., ge=1),
    record_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCommandMutationResponse:
    """Supersede an active military service record for a person."""
    require_hr_import_admin_or_403(user)
    assert_ppr_read_allowed_for_person(user, person_id)
    return _run_mutation(
        lambda: supersede_military_service_by_person(
            user,
            person_id=person_id,
            record_id=record_id,
            body=body,
        ),
        response=response,
        is_create=False,
    )


@router.post(
    "/employees/{employee_id}/military-service/records",
    response_model=PprCommandMutationResponse,
)
def create_military_service_by_employee_route(
    body: PprMilitaryServiceCreateRequest,
    response: Response,
    employee_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCommandMutationResponse:
    """Create military service record via employee_id (identity resolution)."""
    require_hr_import_admin_or_403(user)
    assert_ppr_read_allowed_for_employee(user, employee_id)
    return _run_mutation(
        lambda: create_military_service_by_employee(user, employee_id=employee_id, body=body),
        response=response,
        is_create=True,
    )


@router.post(
    "/employees/{employee_id}/military-service/records/{record_id}/void",
    response_model=PprCommandMutationResponse,
)
def void_military_service_by_employee_route(
    body: PprMilitaryServiceVoidRequest,
    response: Response,
    employee_id: int = Path(..., ge=1),
    record_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCommandMutationResponse:
    """Void an active military service record via employee_id."""
    require_hr_import_admin_or_403(user)
    assert_ppr_read_allowed_for_employee(user, employee_id)
    return _run_mutation(
        lambda: void_military_service_by_employee(
            user,
            employee_id=employee_id,
            record_id=record_id,
            body=body,
        ),
        response=response,
        is_create=False,
    )


@router.post(
    "/employees/{employee_id}/military-service/records/{record_id}/supersede",
    response_model=PprCommandMutationResponse,
)
def supersede_military_service_by_employee_route(
    body: PprMilitaryServiceSupersedeRequest,
    response: Response,
    employee_id: int = Path(..., ge=1),
    record_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprCommandMutationResponse:
    """Supersede an active military service record via employee_id."""
    require_hr_import_admin_or_403(user)
    assert_ppr_read_allowed_for_employee(user, employee_id)
    return _run_mutation(
        lambda: supersede_military_service_by_employee(
            user,
            employee_id=employee_id,
            record_id=record_id,
            body=body,
        ),
        response=response,
        is_create=False,
    )
