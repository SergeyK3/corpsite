"""Operational Orders intake API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.directory.common import as_http500, call_service
from app.operational_orders.errors import (
    OperationalOrderBlockNotFoundError,
    OperationalOrderClarificationNotFoundError,
    OperationalOrderConfirmationConflictError,
    OperationalOrderConfirmationNotFoundError,
    OperationalOrderConfirmationPartyMismatchError,
    OperationalOrderConfirmationStaleTextError,
    OperationalOrderEditorialPackageNotReadyError,
    OperationalOrderForbiddenError,
    OperationalOrderInvalidWorkspaceStageError,
    OperationalOrderReconciliationNotFoundError,
    OperationalOrderReconciliationStaleError,
    OperationalOrderSubmittedTextImmutableError,
    OperationalOrderTranslationAssignmentConflictError,
    OperationalOrderTranslationAssignmentNotFoundError,
    OperationalOrderTranslationSourceStaleError,
    OperationalOrderValidationBlockedError,
    OperationalOrderValidationError,
    OperationalOrderVersionConflictError,
    OperationalOrderWorkspaceNotFoundError,
)
from app.operational_orders.editorial_permissions import (
    can_assign_translation,
    can_confirm_as_content_author,
    can_confirm_content,
    can_mark_editorial_ready,
    can_read_editorial,
    can_reconcile,
    can_work_translation,
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
from app.operational_orders.schemas.editorial_workflow import (
    BilingualReconciliationCreateIn,
    BilingualReconciliationInvalidateIn,
    BilingualReconciliationListOut,
    ContentConfirmationCreateIn,
    ContentConfirmationListOut,
    ContentConfirmationRevokeIn,
    EditorialPackageValidationOut,
    TranslationAssignmentActionIn,
    TranslationAssignmentCompleteIn,
    TranslationAssignmentCreateIn,
    TranslationAssignmentListOut,
)
from app.operational_orders.services import draft_intake_service as svc
from app.operational_orders.services import editorial_workflow_service as editorial_svc
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
    if isinstance(exc, OperationalOrderTranslationAssignmentNotFoundError):
        return HTTPException(status_code=404, detail={"code": code, "message": str(exc)})
    if isinstance(exc, OperationalOrderConfirmationNotFoundError):
        return HTTPException(status_code=404, detail={"code": code, "message": str(exc)})
    if isinstance(exc, OperationalOrderReconciliationNotFoundError):
        return HTTPException(status_code=404, detail={"code": code, "message": str(exc)})
    if isinstance(exc, OperationalOrderForbiddenError):
        return HTTPException(status_code=403, detail={"code": code, "message": str(exc)})
    if isinstance(exc, OperationalOrderVersionConflictError):
        return HTTPException(status_code=409, detail={"code": code, "message": str(exc)})
    if isinstance(
        exc,
        (
            OperationalOrderSubmittedTextImmutableError,
            OperationalOrderInvalidWorkspaceStageError,
            OperationalOrderTranslationAssignmentConflictError,
            OperationalOrderTranslationSourceStaleError,
            OperationalOrderConfirmationPartyMismatchError,
            OperationalOrderConfirmationStaleTextError,
            OperationalOrderConfirmationConflictError,
            OperationalOrderReconciliationStaleError,
            OperationalOrderEditorialPackageNotReadyError,
        ),
    ):
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


@router.post("/draft-workspaces/{workspace_id}/translation-assignments", response_model=DraftWorkspaceDetailOut)
def create_translation_assignment(
    workspace_id: int,
    body: TranslationAssignmentCreateIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_assign_translation(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            editorial_svc.create_translation_assignment,
            workspace_id=workspace_id,
            target_locale=body.target_locale,
            assigned_to_type=body.assigned_to.reference_type,
            assigned_to_reference=body.assigned_to.reference,
            assigned_to_display_name=body.assigned_to.display_name,
            assigned_by_user_id=_require_user_id(user),
            due_at=body.due_at,
            notes=body.notes,
            expected_version=body.expected_version,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.get(
    "/draft-workspaces/{workspace_id}/translation-assignments",
    response_model=TranslationAssignmentListOut,
)
def list_translation_assignments(
    workspace_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_read_editorial(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        result = call_service(editorial_svc.list_translation_assignments, workspace_id=workspace_id)
        return TranslationAssignmentListOut.model_validate(result)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post(
    "/draft-workspaces/{workspace_id}/translation-assignments/{assignment_id}/accept",
    response_model=DraftWorkspaceDetailOut,
)
def accept_translation_assignment(
    workspace_id: int,
    assignment_id: int,
    body: TranslationAssignmentActionIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        assignments = detail.get("translation_assignments", [])
        assignment = next((a for a in assignments if int(a["id"]) == int(assignment_id)), None)
        if not can_work_translation(user, detail["workspace"], assignment):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            editorial_svc.accept_translation_assignment,
            workspace_id=workspace_id,
            assignment_id=assignment_id,
            actor_user_id=_require_user_id(user),
            expected_version=body.expected_version,
            assignment_expected_version=body.assignment_expected_version,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post(
    "/draft-workspaces/{workspace_id}/translation-assignments/{assignment_id}/start",
    response_model=DraftWorkspaceDetailOut,
)
def start_translation_assignment(
    workspace_id: int,
    assignment_id: int,
    body: TranslationAssignmentActionIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        assignments = detail.get("translation_assignments", [])
        assignment = next((a for a in assignments if int(a["id"]) == int(assignment_id)), None)
        if not can_work_translation(user, detail["workspace"], assignment):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            editorial_svc.start_translation_assignment,
            workspace_id=workspace_id,
            assignment_id=assignment_id,
            actor_user_id=_require_user_id(user),
            expected_version=body.expected_version,
            assignment_expected_version=body.assignment_expected_version,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post(
    "/draft-workspaces/{workspace_id}/translation-assignments/{assignment_id}/complete",
    response_model=DraftWorkspaceDetailOut,
)
def complete_translation_assignment(
    workspace_id: int,
    assignment_id: int,
    body: TranslationAssignmentCompleteIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        assignments = detail.get("translation_assignments", [])
        assignment = next((a for a in assignments if int(a["id"]) == int(assignment_id)), None)
        if not can_work_translation(user, detail["workspace"], assignment):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            editorial_svc.complete_translation_assignment,
            workspace_id=workspace_id,
            assignment_id=assignment_id,
            actor_user_id=_require_user_id(user),
            target_block_id=body.target_block_id,
            expected_version=body.expected_version,
            assignment_expected_version=body.assignment_expected_version,
            block_expected_version=body.block_expected_version,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post(
    "/draft-workspaces/{workspace_id}/translation-assignments/{assignment_id}/cancel",
    response_model=DraftWorkspaceDetailOut,
)
def cancel_translation_assignment(
    workspace_id: int,
    assignment_id: int,
    body: TranslationAssignmentActionIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_assign_translation(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            editorial_svc.cancel_translation_assignment,
            workspace_id=workspace_id,
            assignment_id=assignment_id,
            actor_user_id=_require_user_id(user),
            expected_version=body.expected_version,
            assignment_expected_version=body.assignment_expected_version,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.get(
    "/draft-workspaces/{workspace_id}/confirmations",
    response_model=ContentConfirmationListOut,
)
def list_content_confirmations(
    workspace_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_read_editorial(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        result = call_service(editorial_svc.list_content_confirmations, workspace_id=workspace_id)
        return ContentConfirmationListOut.model_validate(result)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post("/draft-workspaces/{workspace_id}/confirmations", response_model=DraftWorkspaceDetailOut)
def create_content_confirmation(
    workspace_id: int,
    body: ContentConfirmationCreateIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if body.confirmation_role == "CONTENT_AUTHOR":
            if not can_confirm_as_content_author(user, detail["workspace"]) and not (
                body.operator_recorded and can_confirm_content(user, detail["workspace"])
            ):
                raise OperationalOrderForbiddenError("Access denied.")
        elif not can_confirm_content(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            editorial_svc.create_content_confirmation,
            workspace_id=workspace_id,
            block_id=body.block_id,
            confirmation_role=body.confirmation_role,
            confirmer_party_type=body.confirmer.reference_type,
            confirmer_party_reference=body.confirmer.reference,
            confirmer_display_name=body.confirmer.display_name,
            confirmer_user_id=_require_user_id(user),
            block_expected_version=body.block_expected_version,
            expected_version=body.expected_version,
            operator_recorded=body.operator_recorded,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post(
    "/draft-workspaces/{workspace_id}/confirmations/{confirmation_id}/revoke",
    response_model=DraftWorkspaceDetailOut,
)
def revoke_content_confirmation(
    workspace_id: int,
    confirmation_id: int,
    body: ContentConfirmationRevokeIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_confirm_content(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            editorial_svc.revoke_content_confirmation,
            workspace_id=workspace_id,
            confirmation_id=confirmation_id,
            actor_user_id=_require_user_id(user),
            revocation_reason=body.revocation_reason,
            expected_version=body.expected_version,
            confirmation_expected_version=body.confirmation_expected_version,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.get(
    "/draft-workspaces/{workspace_id}/reconciliations",
    response_model=BilingualReconciliationListOut,
)
def list_bilingual_reconciliations(
    workspace_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_read_editorial(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        result = call_service(editorial_svc.list_bilingual_reconciliations, workspace_id=workspace_id)
        return BilingualReconciliationListOut.model_validate(result)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post("/draft-workspaces/{workspace_id}/reconciliations", response_model=DraftWorkspaceDetailOut)
def create_bilingual_reconciliation(
    workspace_id: int,
    body: BilingualReconciliationCreateIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_reconcile(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            editorial_svc.create_bilingual_reconciliation,
            workspace_id=workspace_id,
            ru_block_id=body.ru_block_id,
            kk_block_id=body.kk_block_id,
            reconciled_by_user_id=_require_user_id(user),
            notes=body.notes,
            ru_block_expected_version=body.ru_block_expected_version,
            kk_block_expected_version=body.kk_block_expected_version,
            expected_version=body.expected_version,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post(
    "/draft-workspaces/{workspace_id}/reconciliations/{reconciliation_id}/invalidate",
    response_model=DraftWorkspaceDetailOut,
)
def invalidate_bilingual_reconciliation(
    workspace_id: int,
    reconciliation_id: int,
    body: BilingualReconciliationInvalidateIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_reconcile(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            editorial_svc.invalidate_bilingual_reconciliation,
            workspace_id=workspace_id,
            reconciliation_id=reconciliation_id,
            actor_user_id=_require_user_id(user),
            invalidation_reason=body.invalidation_reason,
            expected_version=body.expected_version,
            reconciliation_expected_version=body.reconciliation_expected_version,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post(
    "/draft-workspaces/{workspace_id}/validate-editorial-package",
    response_model=EditorialPackageValidationOut,
)
def validate_editorial_package_endpoint(
    workspace_id: int,
    body: VersionedActionIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_read_editorial(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        result = call_service(
            editorial_svc.validate_editorial_package_command,
            workspace_id=workspace_id,
            expected_version=body.expected_version,
        )
        validation = result["validation"]
        return EditorialPackageValidationOut(
            workspace_id=int(result["workspace_id"]),
            validation=mappers._validation_out(validation),
        )
    except Exception as exc:
        raise _domain_http(exc) from exc


@router.post("/draft-workspaces/{workspace_id}/editorial-package-ready", response_model=DraftWorkspaceDetailOut)
def editorial_package_ready(
    workspace_id: int,
    body: VersionedActionIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        detail = call_service(svc.get_workspace, workspace_id=workspace_id)
        if not can_mark_editorial_ready(user, detail["workspace"]):
            raise OperationalOrderForbiddenError("Access denied.")
        detail = call_service(
            editorial_svc.mark_editorial_package_ready,
            workspace_id=workspace_id,
            actor_user_id=_require_user_id(user),
            expected_version=body.expected_version,
        )
        return mappers.to_detail_out(detail)
    except Exception as exc:
        raise _domain_http(exc) from exc
