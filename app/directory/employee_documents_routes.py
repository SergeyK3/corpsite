# FILE: app/directory/employee_documents_routes.py
"""ADR-037 Phase 1A: production employee documents registry routes."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from app.auth import get_current_user
from app.services.employee_documents_service import (
    EmployeeDocumentNotFoundError,
    EmployeeDocumentValidationError,
    create_employee_document,
    get_employee_document,
    list_document_kinds,
    list_document_types,
    list_employee_documents,
    list_medical_specialties,
    list_medical_specialty_groups,
    soft_delete_employee_document,
    update_employee_document,
)

from .common import as_http500, call_service
from .rbac import require_privileged_or_403

router = APIRouter()


class EmployeeDocumentCreateIn(BaseModel):
    employee_id: int = Field(..., ge=1)
    document_type_id: int = Field(..., ge=1)
    document_kind_id: Optional[int] = Field(default=None, ge=1)
    medical_specialty_id: Optional[int] = Field(default=None, ge=1)
    title: Optional[str] = Field(default=None, max_length=500)
    training_title: Optional[str] = Field(default=None, max_length=500)
    document_number: Optional[str] = Field(default=None, max_length=200)
    issued_by: Optional[str] = Field(default=None, max_length=500)
    issued_at: Optional[date] = None
    valid_until: Optional[date] = None
    file_url: Optional[str] = Field(default=None, max_length=2000)
    comment: Optional[str] = Field(default=None, max_length=2000)
    lifecycle_status: Optional[str] = Field(default=None, max_length=20)


class EmployeeDocumentUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type_id: Optional[int] = Field(default=None, ge=1)
    document_kind_id: Optional[int] = Field(default=None, ge=1)
    clear_document_kind: bool = False
    medical_specialty_id: Optional[int] = Field(default=None, ge=1)
    clear_medical_specialty: bool = False
    title: Optional[str] = Field(default=None, max_length=500)
    training_title: Optional[str] = Field(default=None, max_length=500)
    document_number: Optional[str] = Field(default=None, max_length=200)
    issued_by: Optional[str] = Field(default=None, max_length=500)
    issued_at: Optional[date] = None
    valid_until: Optional[date] = None
    clear_valid_until: bool = False
    file_url: Optional[str] = Field(default=None, max_length=2000)
    clear_file_url: bool = False
    comment: Optional[str] = Field(default=None, max_length=2000)
    lifecycle_status: Optional[str] = Field(default=None, max_length=20)


def _validation_http422(exc: EmployeeDocumentValidationError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


def _require_user_id(user: Dict[str, Any]) -> int:
    uid = user.get("user_id") or user.get("id")
    if uid is None:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return int(uid)


@router.get("/document-types")
def get_document_types(
    is_active: bool = Query(default=True),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return call_service(list_document_types, is_active=is_active)
    except Exception as e:
        raise as_http500(e)


@router.get("/document-kinds")
def get_document_kinds(
    is_active: bool = Query(default=True),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return call_service(list_document_kinds, is_active=is_active)
    except Exception as e:
        raise as_http500(e)


@router.get("/medical-specialty-groups")
def get_medical_specialty_groups(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return call_service(list_medical_specialty_groups)
    except Exception as e:
        raise as_http500(e)


@router.get("/medical-specialties")
def get_medical_specialties(
    group_id: Optional[int] = Query(default=None, ge=1),
    group_code: Optional[str] = Query(default=None),
    is_active: bool = Query(default=True),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return call_service(
            list_medical_specialties,
            group_id=group_id,
            group_code=group_code,
            is_active=is_active,
        )
    except Exception as e:
        raise as_http500(e)


@router.get("/employee-documents")
def get_employee_documents(
    employee_id: Optional[int] = Query(default=None, ge=1),
    employee_is_active: Optional[bool] = Query(default=None),
    document_type_id: Optional[int] = Query(default=None, ge=1),
    medical_specialty_id: Optional[int] = Query(default=None, ge=1),
    group_id: Optional[int] = Query(default=None, ge=1),
    lifecycle_status: str = Query(default="ACTIVE"),
    expiry_status: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return call_service(
            list_employee_documents,
            employee_id=employee_id,
            employee_is_active=employee_is_active,
            document_type_id=document_type_id,
            medical_specialty_id=medical_specialty_id,
            group_id=group_id,
            lifecycle_status=lifecycle_status,
            expiry_status=expiry_status,
            q=q,
            limit=limit,
            offset=offset,
        )
    except EmployeeDocumentValidationError as e:
        raise _validation_http422(e)
    except Exception as e:
        raise as_http500(e)


@router.get("/employee-documents/{document_id}")
def get_employee_document_route(
    document_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        item = call_service(get_employee_document, document_id=document_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Document not found.")
        return item
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.post("/employee-documents", status_code=201)
def post_employee_document(
    payload: EmployeeDocumentCreateIn,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return call_service(
            create_employee_document,
            employee_id=payload.employee_id,
            document_type_id=payload.document_type_id,
            document_kind_id=payload.document_kind_id,
            medical_specialty_id=payload.medical_specialty_id,
            title=payload.title,
            training_title=payload.training_title,
            document_number=payload.document_number,
            issued_by=payload.issued_by,
            issued_at=payload.issued_at,
            valid_until=payload.valid_until,
            file_url=payload.file_url,
            comment=payload.comment,
            lifecycle_status=payload.lifecycle_status,
            created_by=_require_user_id(user),
        )
    except EmployeeDocumentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except EmployeeDocumentValidationError as e:
        raise _validation_http422(e)
    except Exception as e:
        raise as_http500(e)


@router.put("/employee-documents/{document_id}")
def put_employee_document(
    payload: EmployeeDocumentUpdateIn,
    document_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    if not payload.model_dump(exclude_unset=True):
        raise HTTPException(status_code=422, detail="At least one field must be provided.")
    try:
        item = call_service(
            update_employee_document,
            document_id=document_id,
            document_type_id=payload.document_type_id,
            document_kind_id=payload.document_kind_id,
            clear_document_kind=payload.clear_document_kind,
            medical_specialty_id=payload.medical_specialty_id,
            clear_medical_specialty=payload.clear_medical_specialty,
            title=payload.title,
            training_title=payload.training_title,
            document_number=payload.document_number,
            issued_by=payload.issued_by,
            issued_at=payload.issued_at,
            valid_until=payload.valid_until,
            clear_valid_until=payload.clear_valid_until,
            file_url=payload.file_url,
            clear_file_url=payload.clear_file_url,
            comment=payload.comment,
            lifecycle_status=payload.lifecycle_status,
        )
        if item is None:
            raise HTTPException(status_code=404, detail="Document not found.")
        return item
    except EmployeeDocumentValidationError as e:
        raise _validation_http422(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.delete("/employee-documents/{document_id}")
def delete_employee_document(
    document_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        item = call_service(soft_delete_employee_document, document_id=document_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Document not found.")
        return item
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)
