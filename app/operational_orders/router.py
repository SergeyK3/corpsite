"""Operational Orders intake API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.directory.common import as_http500, call_service
from app.operational_orders.errors import (
    OperationalOrderBlockNotFoundError,
    OperationalOrderClarificationNotFoundError,
    OperationalOrderForbiddenError,
    OperationalOrderInvalidWorkspaceStageError,
    OperationalOrderSubmittedTextImmutableError,
    OperationalOrderValidationBlockedError,
    OperationalOrderValidationError,
    OperationalOrderVersionConflictError,
    OperationalOrderWorkspaceNotFoundError,
)
from app.operational_orders.permissions import (
    PERMISSION_INTAKE_OPERATE,
    can_create_intake,
    can_operate_intake,
    can_read_workspace,
)
from app.operational_orders.scope import assert_submitting_unit_in_scope, resolve_user_scope_unit_ids
from app.security.admin_permissions import has_admin_permission
from app.security.directory_scope import is_privileged
from app.operational_orders.schemas.draft_workspace import (
    ClarificationResolveIn,
    DraftBlockAddIn,
    DraftBlockEffectivePatchIn,
    DraftWorkspaceCreateIn,
    DraftWorkspaceDetailOut,
    DraftWorkspaceListOut,
    VersionedActionIn,
)
from app.operational_orders.services import draft_intake_service as svc
from app.operational_orders.schemas import mappers

router = APIRouter(prefix="/api/operational-orders", tags=["operational-orders"])


def _require_user_id(user: dict[str, Any]) -> int:
    uid = user.get("user_id") or user.get("id")
    if uid is None:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return int(uid)


def _domain_http(exc: Exception) -> HTTPException:
    code = getattr(exc, "code", "OO_ERROR")
    if isinstance(exc, OperationalOrderWorkspaceNotFoundError):
        return HTTPException(status_code=404, detail={"code": code, "message": str(exc)})
    if isinstance(exc, OperationalOrderBlockNotFoundError):
        return HTTPException(status_code=404, detail={"code": code, "message": str(exc)})
    if isinstance(exc, OperationalOrderClarificationNotFoundError):
        return HTTPException(status_code=404, detail={"code": code, "message": str(exc)})
    if isinstance(exc, OperationalOrderForbiddenError):
        return HTTPException(status_code=403, detail={"code": code, "message": str(exc)})
    if isinstance(exc, OperationalOrderVersionConflictError):
        return HTTPException(status_code=409, detail={"code": code, "message": str(exc)})
    if isinstance(exc, (OperationalOrderSubmittedTextImmutableError, OperationalOrderInvalidWorkspaceStageError)):
        return HTTPException(status_code=409, detail={"code": code, "message": str(exc)})
    if isinstance(exc, (OperationalOrderValidationBlockedError, OperationalOrderValidationError)):
        status = 422 if isinstance(exc, OperationalOrderValidationError) else 409
        return HTTPException(status_code=status, detail={"code": code, "message": str(exc)})
    return as_http500(exc)


@router.post("/draft-workspaces", response_model=DraftWorkspaceDetailOut)
def create_draft_workspace(
    body: DraftWorkspaceCreateIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    if not can_create_intake(user):
        raise HTTPException(status_code=403, detail={"code": "OO_FORBIDDEN", "message": "Access denied."})
    try:
        assert_submitting_unit_in_scope(user, body.submitting_org_unit_id)
        detail = call_service(
            svc.create_submission,
            initiator_type=body.initiator.reference_type,
            initiator_reference=body.initiator.reference,
            initiator_display_name=body.initiator.display_name,
            content_author_type=body.content_author.reference_type,
            content_author_reference=body.content_author.reference,
            content_author_display_name=body.content_author.display_name,
            submitting_org_unit_id=body.submitting_org_unit_id,
            record_creator_user_id=_require_user_id(user),
            blocks=[block.model_dump() for block in body.blocks],
            organization_id=body.organization_id,
            proposed_title=body.proposed_title,
            proposed_signer_type=body.proposed_signer.reference_type if body.proposed_signer else None,
            proposed_signer_reference=body.proposed_signer.reference if body.proposed_signer else None,
            proposed_signer_display_name=body.proposed_signer.display_name if body.proposed_signer else None,
            source_language=body.source_language,
            required_locales=body.required_locales,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.get("/draft-workspaces", response_model=DraftWorkspaceListOut)
def list_draft_workspaces(
    stage: str | None = Query(default=None),
    submitting_org_unit_id: int | None = Query(default=None),
    record_creator_user_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
):
    creator_filter = record_creator_user_id
    user_id = _require_user_id(user)
    scope_unit_ids = resolve_user_scope_unit_ids(user)
    if creator_filter is None and not (
        is_privileged(user) or has_admin_permission(user_id, PERMISSION_INTAKE_OPERATE)
    ):
        creator_filter = user_id
    try:
        result = call_service(
            svc.list_workspaces,
            stage=stage,
            submitting_org_unit_id=submitting_org_unit_id,
            record_creator_user_id=creator_filter,
            scope_unit_ids=sorted(scope_unit_ids) if scope_unit_ids is not None else None,
            limit=limit,
            offset=offset,
        )
        return mappers.to_list_out(result)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.get("/draft-workspaces/{workspace_id}", response_model=DraftWorkspaceDetailOut)
def get_draft_workspace(
    workspace_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_read_workspace(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post("/draft-workspaces/{workspace_id}/accept", response_model=DraftWorkspaceDetailOut)
def accept_draft_workspace(
    workspace_id: int,
    body: VersionedActionIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_operate_intake(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            svc.accept_submission,
            workspace_id=workspace_id,
            actor_user_id=_require_user_id(user),
            expected_version=body.expected_version,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post("/draft-workspaces/{workspace_id}/blocks", response_model=DraftWorkspaceDetailOut)
def add_draft_block(
    workspace_id: int,
    body: DraftBlockAddIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_operate_intake(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            svc.add_draft_block,
            workspace_id=workspace_id,
            locale=body.locale,
            block_type=body.block_type,
            submitted_text=body.submitted_text,
            source_type=body.source_type,
            sequence=body.sequence,
            actor_user_id=_require_user_id(user),
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.patch("/draft-workspaces/{workspace_id}/blocks/{block_id}", response_model=DraftWorkspaceDetailOut)
def patch_draft_block_effective_text(
    workspace_id: int,
    block_id: int,
    body: DraftBlockEffectivePatchIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_operate_intake(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            svc.update_workspace_effective_text,
            workspace_id=workspace_id,
            block_id=block_id,
            workspace_effective_text=body.workspace_effective_text,
            actor_user_id=_require_user_id(user),
            expected_version=body.expected_version,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post("/draft-workspaces/{workspace_id}/validate", response_model=DraftWorkspaceDetailOut)
def validate_draft_workspace(
    workspace_id: int,
    body: VersionedActionIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_operate_intake(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            svc.run_intake_validation,
            workspace_id=workspace_id,
            actor_user_id=_require_user_id(user),
            expected_version=body.expected_version,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post(
    "/draft-workspaces/{workspace_id}/clarifications/{clarification_id}/resolve",
    response_model=DraftWorkspaceDetailOut,
)
def resolve_clarification(
    workspace_id: int,
    clarification_id: int,
    body: ClarificationResolveIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_operate_intake(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            svc.resolve_clarification,
            workspace_id=workspace_id,
            clarification_id=clarification_id,
            actor_user_id=_require_user_id(user),
            resolution_note=body.resolution_note,
            expected_version=body.expected_version,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post("/draft-workspaces/{workspace_id}/ready-for-editorial", response_model=DraftWorkspaceDetailOut)
def ready_for_editorial(
    workspace_id: int,
    body: VersionedActionIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_operate_intake(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            svc.mark_ready_for_editorial,
            workspace_id=workspace_id,
            actor_user_id=_require_user_id(user),
            expected_version=body.expected_version,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc
