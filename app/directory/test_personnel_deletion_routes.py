"""WP-TD-002 API. There is deliberately no execution/delete endpoint here."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder

from app.auth import get_current_user
from app.services.ppr_query_access_service import assert_ppr_read_allowed_for_person
from app.security.admin_permissions import (
    TEST_PERSONNEL_DELETION_APPROVE,
    TEST_PERSONNEL_DELETION_AUDIT_READ,
    TEST_PERSONNEL_DELETION_REQUEST,
    has_admin_permission,
)
from app.services import test_personnel_deletion_service as service

from .test_personnel_deletion_schemas import (
    TestPersonnelCommandIn,
    TestPersonnelDecisionIn,
    TestPersonnelDraftCreateIn,
    TestPersonnelPreviewIn,
)

router = APIRouter(prefix="/test-personnel-deletion", tags=["test-personnel-deletion"])


def _error(exc: service.TestPersonnelDeletionError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message})


def _require(user: dict[str, Any], permission: str, role_code: str) -> int:
    user_id = int(user["user_id"])
    if service.actor_role_code(user_id) != role_code or not has_admin_permission(user_id, permission):
        raise HTTPException(status_code=403, detail={"code": "TD_PERMISSION_REQUIRED", "permission": permission})
    return user_id


def _scope_hr_detail(user: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    for target in detail.get("targets", []):
        assert_ppr_read_allowed_for_person(user, int(target["person_id"]))
        # No canonical permission dedicated to full-IIN disclosure exists yet.
        # WP-TD-002B therefore always returns the masked representation.
        target["subject"] = service.safe_identity(int(target["person_id"]))
    return detail


def _authorize_detail(user: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    actor = int(user["user_id"])
    role = service.actor_role_code(actor)
    if role == "ADMIN" and int(detail["initiated_by_user_id"]) == actor and has_admin_permission(actor, TEST_PERSONNEL_DELETION_REQUEST):
        return detail
    if role == "ADMIN" and has_admin_permission(actor, TEST_PERSONNEL_DELETION_AUDIT_READ):
        return detail
    if role == "HR_HEAD" and (has_admin_permission(actor, TEST_PERSONNEL_DELETION_APPROVE) or has_admin_permission(actor, TEST_PERSONNEL_DELETION_AUDIT_READ)):
        return _scope_hr_detail(user, detail)
    raise HTTPException(status_code=404, detail={"code": "TD_REQUEST_NOT_FOUND"})


@router.post("/preview")
def preview(body: TestPersonnelPreviewIn, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    _require(user, TEST_PERSONNEL_DELETION_REQUEST, "ADMIN")
    try:
        return service.preview_candidates(
            mask=body.mask,
            field=body.field,
            person_ids=body.person_ids,
            application_ids=body.application_ids,
        )
    except service.TestPersonnelDeletionError as exc:
        raise _error(exc) from exc


@router.post("/requests", status_code=201)
def create_request(body: TestPersonnelDraftCreateIn, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    actor = _require(user, TEST_PERSONNEL_DELETION_REQUEST, "ADMIN")
    try:
        return service.create_draft(
            actor_user_id=actor,
            basis=body.basis,
            reason_code=body.reason_code,
            preview_criteria={"field": body.search_field, "selection": "EXACT_MANIFEST"},
            original_mask=body.original_mask,
            targets=[target.model_dump() for target in body.targets],
            idempotency_key=body.idempotency_key,
        )
    except service.TestPersonnelDeletionError as exc:
        raise _error(exc) from exc


@router.get("/requests")
def requests(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    actor = _require(user, TEST_PERSONNEL_DELETION_REQUEST, "ADMIN")
    audit_reader = has_admin_permission(actor, TEST_PERSONNEL_DELETION_AUDIT_READ)
    return {"items": service.list_requests(initiator_user_id=None if audit_reader else actor)}


@router.get("/requests/{request_id}")
def request_detail(request_id: UUID, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return _authorize_detail(user, service.get_request(request_id))
    except service.TestPersonnelDeletionError as exc:
        raise _error(exc) from exc


@router.post("/requests/{request_id}/submit")
def submit(request_id: UUID, body: TestPersonnelCommandIn, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    actor = _require(user, TEST_PERSONNEL_DELETION_REQUEST, "ADMIN")
    try:
        result, conflict = service.submit_request(
            request_id=request_id, actor_user_id=actor, expected_version=body.expected_version,
            idempotency_key=body.idempotency_key,
        )
        if conflict:
            raise HTTPException(status_code=409, detail={"code": conflict, "request": jsonable_encoder(result)})
        return result
    except service.TestPersonnelDeletionError as exc:
        raise _error(exc) from exc


@router.post("/requests/{request_id}/cancel")
def cancel(request_id: UUID, body: TestPersonnelCommandIn, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    actor = _require(user, TEST_PERSONNEL_DELETION_REQUEST, "ADMIN")
    try:
        return service.cancel_request(
            request_id=request_id, actor_user_id=actor, expected_version=body.expected_version,
            idempotency_key=body.idempotency_key, comment=body.comment,
        )
    except service.TestPersonnelDeletionError as exc:
        raise _error(exc) from exc


@router.get("/approvals")
def approvals(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    _require(user, TEST_PERSONNEL_DELETION_APPROVE, "HR_HEAD")
    visible = []
    for item in service.list_requests(pending_only=True):
        try:
            visible.append(_scope_hr_detail(user, service.get_request(item["request_id"])))
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
    return {"items": visible}


@router.get("/approvals/{request_id}")
def approval_detail(request_id: UUID, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    _require(user, TEST_PERSONNEL_DELETION_APPROVE, "HR_HEAD")
    try:
        return _scope_hr_detail(user, service.get_request(request_id))
    except service.TestPersonnelDeletionError as exc:
        raise _error(exc) from exc


def _decide(request_id: UUID, body: TestPersonnelDecisionIn, user: dict[str, Any], decision: str) -> dict[str, Any]:
    actor = _require(user, TEST_PERSONNEL_DELETION_APPROVE, "HR_HEAD")
    try:
        result, conflict = service.decide_request(
            request_id=request_id, actor_user_id=actor, expected_version=body.expected_version,
            decision=decision, idempotency_key=body.idempotency_key, comment=body.comment,
            submitted_synthetic_confirmed=body.submitted_synthetic_confirmed,
        )
        if conflict:
            raise HTTPException(status_code=409, detail={"code": conflict, "request": jsonable_encoder(result)})
        return result
    except service.TestPersonnelDeletionError as exc:
        raise _error(exc) from exc


@router.post("/approvals/{request_id}/approve")
def approve(request_id: UUID, body: TestPersonnelDecisionIn, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _decide(request_id, body, user, "APPROVE")


@router.post("/approvals/{request_id}/reject")
def reject(request_id: UUID, body: TestPersonnelDecisionIn, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _decide(request_id, body, user, "REJECT")
