# FILE: app/directory/personnel_orders_routes.py
"""Personnel orders API: read (WP-PO-004A), draft/register (WP-PO-004B), apply (WP-PO-004C), void (WP-PO-004D)."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.directory.common import as_http500, call_service
from app.directory.personnel_orders_schemas import (
    EditorialBlockPatchIn,
    EditorialGenerateIn,
    EditorialStateResponse,
    PersonnelOrderCancelIn,
    PersonnelOrderArchiveIn,
    PersonnelOrderAcknowledgementClearIn,
    PersonnelOrderAcknowledgementListResponse,
    PersonnelOrderAcknowledgementRecordIn,
    PersonnelOrderCreateIn,
    PersonnelOrderDetailResponse,
    PersonnelOrderDocumentReviewConfirmIn,
    PersonnelOrderDocumentReviewOut,
    PersonnelOrderDocumentReviewReopenIn,
    PersonnelOrderDocumentHeaderPatchIn,
    PersonnelOrderHeaderDuplicatePreviewIn,
    PersonnelOrderDocumentItemPatchIn,
    PersonnelOrderDocumentItemListResponse,
    PersonnelOrderManualDraftCreateIn,
    PersonnelOrderManualDraftCreateOut,
    PersonnelOrderPublishedTemplateTitleOut,
    PersonnelOrderItemCreateIn,
    PersonnelOrderItemUpdateIn,
    PersonnelOrderLifecycleAuditListResponse,
    PersonnelOrderListResponse,
    PersonnelOrderLocalizedTextUpsertIn,
    PersonnelOrderRegisterIn,
    PersonnelOrderRestoreIn,
    PersonnelOrderSignatoryDefaultOut,
    PersonnelOrderUpdateIn,
    PersonnelOrderTemplateApplicationIn,
    PersonnelOrderTemplateApplicationPreviewOut,
    PersonnelOrderVoidIn,
)
from app.directory.rbac import compute_scope, require_personnel_admin_or_403, require_personnel_visibility_or_403
from app.person_photos.domain.errors import HirePhotoNotReadyError
from app.services.personnel_order_archive_guard import PersonnelOrderArchivedError
from app.services.personnel_orders_apply_service import (
    PersonnelOrderAlreadyAppliedError,
    apply_personnel_order,
)
from app.services.personnel_orders_cancel_service import (
    PersonnelOrderCancelError,
    cancel_personnel_order,
)
from app.services.personnel_orders_archive_service import (
    PersonnelOrderArchiveError,
    archive_personnel_order,
    restore_personnel_order,
)
from app.services.personnel_orders_void_service import (
    PersonnelOrderAlreadyVoidedError,
    PersonnelOrderItemAlreadyVoidedError,
    PersonnelOrderVoidChainError,
    void_personnel_order,
    void_personnel_order_item,
)
from app.services.personnel_orders_command_service import (
    PersonnelOrderConflictError,
    PersonnelOrderDeletedError,
    PersonnelOrderItemNotFoundError,
    create_personnel_order_draft,
    delete_personnel_order_item,
    create_personnel_order_item,
    mark_personnel_order_ready_for_signature,
    register_personnel_order,
    update_personnel_order_draft,
    update_personnel_order_item,
    upsert_personnel_order_localized_text,
)
from app.services import personnel_order_draft_deletion_service as draft_deletion
from app.services.personnel_order_quality_control_service import list_personnel_order_quality_issues
from app.services.personnel_order_tombstone_service import get_deleted_personnel_order_tombstone
from app.security.admin_permissions import has_technical_personnel_order_cleanup_permission
from app.services.personnel_orders_editorial_service import (
    PersonnelOrderEditorialBlockNotFoundError,
    PersonnelOrderEditorialConflictError,
    PersonnelOrderReadyGateError,
    generate_editorial,
    get_editorial_state,
    patch_editorial_block,
    reset_block_to_generated,
)
from app.services.personnel_order_template_application_service import TemplateApplicationError, preview_template_application, apply_template_application
from app.services.personnel_orders_query_service import (
    PersonnelOrderNotFoundError,
    PersonnelOrderValidationError,
    get_personnel_order,
    get_default_personnel_order_signatory,
    list_personnel_orders,
    validation_error_to_http422,
)
from app.services.personnel_order_lifecycle_audit_service import (
    list_personnel_order_lifecycle_audit,
)
from app.services.personnel_order_document_review_service import (
    PersonnelOrderDocumentReviewConflictError,
    PersonnelOrderDocumentReviewValidationError,
    get_document_review,
    mutate_document_review,
)
from app.services.personnel_order_document_header_service import duplicate_preview, patch_document_header, PersonnelOrderDuplicateError
from app.services.personnel_order_document_item_service import list_document_items, patch_document_item
from app.services.personnel_order_manual_draft_service import create_manual_draft
from app.services.personnel_order_template_draft_service import TemplateDraftError, get_published, list_templates
from app.db.models.personnel_orders import (
    LIFECYCLE_AUDIT_ACTION_DOCUMENT_CONFIRMED,
    LIFECYCLE_AUDIT_ACTION_DOCUMENT_REOPENED,
)
from app.services.personnel_order_acknowledgement_service import (
    PersonnelOrderAcknowledgementError,
    clear as clear_acknowledgement,
    list_current as list_current_acknowledgements,
    record as record_acknowledgement,
)

router = APIRouter()


class PersonnelOrderDraftDeleteIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    confirmation_phrase: str = Field(min_length=1, max_length=200)


def _require_hr_head_order_delete_or_403(user: Dict[str, Any]) -> None:
    """The exceptional all-status physical delete is reserved for ADMIN/HR_HEAD."""
    require_personnel_admin_or_403(user)
    if str(user.get("role_code") or "").upper() not in {"ADMIN", "HR_HEAD"}:
        raise HTTPException(status_code=403, detail="ADMIN or HR_HEAD access required.")


def _draft_order_scope_or_403(user: Dict[str, Any]) -> list[int] | None:
    """Resolve the effective HR visibility scope for a destructive draft action."""
    scope = compute_scope(int(user["user_id"]), user)
    require_personnel_visibility_or_403(user, scope)
    return None if scope.get("scope_unit_ids") is None else list(scope["scope_unit_ids"])


def _require_system_quality_control_or_403(user: Dict[str, Any]) -> None:
    # Quality control is a system-administrator read model, not a second HR editor.
    if not bool(user.get("is_system_admin")) or not bool(user.get("has_sysadmin_api")):
        raise HTTPException(status_code=403, detail="System administrator access required.")


def _require_deleted_order_tombstone_access_or_403(user: Dict[str, Any]) -> None:
    if (not bool(user.get("is_system_admin")) or not bool(user.get("has_sysadmin_api"))
            or not has_technical_personnel_order_cleanup_permission(int(user["user_id"]))):
        raise HTTPException(status_code=403, detail="System administrator cleanup access required.")


@router.get("/personnel-orders/quality-control")
def personnel_order_quality_control_route(
    limit: int = Query(25, ge=1, le=50),
    offset: int = Query(0, ge=0),
    reason: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    order_type_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Live read-only list of strict personnel-order quality issues."""
    _require_system_quality_control_or_403(user)
    try:
        return list_personnel_order_quality_issues(limit=limit, offset=offset, reason=reason, status=status, order_type_code=order_type_code, q=q)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise as_http500(exc)


@router.get("/personnel-orders/templates/{item_type_code}/published-variants")
def get_personnel_order_published_variants(item_type_code: str, _user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    require_personnel_admin_or_403(_user)
    try:
        from app.db.engine import engine
        from app.services.personnel_order_creation_schema import creation_capabilities
        with engine.connect() as conn:
            capabilities=creation_capabilities(conn,item_type_code)
        public_capabilities={key:capabilities[key] for key in ('independent_supported','creation_supported','creation_reason','schema_mode')}
        if not capabilities['independent_supported']:
            return {"items":[],**public_capabilities}
        rows = list_templates(item_type_code, published_only=True)
        keys = ("template_id", "template_version_id", "version_number", "name_ru", "name_kk", "title_ru", "title_kk", "is_default")
        from app.services.personnel_order_replacement_contract import variant, optional_placement
        from app.services.personnel_order_service_area_contract import enabled
        return {"items": [{**{key: row[key] for key in keys}, "replacement_mode": variant(row), "replacement_optional_placement": optional_placement(row), "service_area_allowance": enabled(row)} for row in rows],**public_capabilities}
    except TemplateDraftError as exc:
        raise validation_error_to_http422(PersonnelOrderValidationError(str(exc))) from exc


@router.get("/personnel-orders/templates/{item_type_code}/published-title", response_model=PersonnelOrderPublishedTemplateTitleOut)
def get_personnel_order_published_template_title(item_type_code: str, _user: Dict[str, Any] = Depends(get_current_user), template_version_id: Annotated[int | None, Query(ge=1)] = None) -> Dict[str, Any]:
    require_personnel_admin_or_403(_user)
    try:
        if template_version_id is None:
            template = get_published(item_type_code)
        else:
            from app.db.engine import engine
            from sqlalchemy import text
            with engine.connect() as conn:
                template = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE template_version_id=:id AND item_type_code=:type AND status='PUBLISHED'"), {"id": template_version_id, "type": item_type_code}).mappings().first()
    except TemplateDraftError as exc:
        raise validation_error_to_http422(PersonnelOrderValidationError(str(exc))) from exc
    if template is None:
        raise HTTPException(status_code=404, detail={"code": "PUBLISHED_TEMPLATE_NOT_FOUND"})
    return {"template_version_id": template.get("template_version_id"), "item_type_code": template["item_type_code"], "title_ru": template["title_ru"], "title_kk": template["title_kk"]}


@router.post("/personnel-orders/manual-draft", response_model=PersonnelOrderManualDraftCreateOut, status_code=201)
def create_manual_personnel_order_draft_route(payload: PersonnelOrderManualDraftCreateIn, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    require_personnel_admin_or_403(user)
    try:
        return call_service(create_manual_draft, created_by=_require_user_id(user), **payload.model_dump(exclude_none=True))
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        if isinstance(exc,PersonnelOrderDuplicateError):raise _conflict_http409(exc)
        raise HTTPException(status_code=409, detail={"code": str(exc)})


def _require_user_id(user: Dict[str, Any]) -> int:
    uid = user.get("user_id") or user.get("id")
    if uid is None:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return int(uid)


def _order_archived_http(exc: PersonnelOrderArchivedError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": exc.code, "message": str(exc)},
    )


def _conflict_http409(exc: PersonnelOrderConflictError) -> HTTPException:
    if isinstance(exc, PersonnelOrderDuplicateError):
        return HTTPException(status_code=409,detail={'code':'DUPLICATE_ORDER_NUMBER_DATE','message':exc.message,'duplicate':exc.duplicate})
    if isinstance(exc, PersonnelOrderDeletedError):
        return HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": exc.message},
        )
    return HTTPException(status_code=409, detail=str(exc))


def _acknowledgement_http(exc: PersonnelOrderAcknowledgementError) -> HTTPException:
    code = str(exc)
    status = 422 if code == "ACKNOWLEDGEMENT_DATE_OUT_OF_RANGE" else 409 if code == "ACKNOWLEDGEMENT_SCHEMA_UNAVAILABLE" else 422
    return HTTPException(status_code=status, detail={"code": code, "message": code})


def _deleted_order_http(exc: PersonnelOrderDeletedError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": exc.code, "message": exc.message},
    )


def _cancel_error_http(exc: PersonnelOrderCancelError) -> HTTPException:
    status_by_code = {
        "ORDER_NOT_CANCELLABLE": 409,
        "ORDER_ALREADY_VOIDED": 409,
        "ORDER_ALREADY_APPLIED": 409,
        "CANCEL_PERMISSION_DENIED": 403,
        "CANCEL_SCOPE_DENIED": 403,
        "INVALID_CANCEL_REASON": 422,
    }
    return HTTPException(
        status_code=status_by_code.get(exc.code, 409),
        detail={"code": exc.code, "message": str(exc)},
    )


def _archive_error_http(exc: PersonnelOrderArchiveError) -> HTTPException:
    status_by_code = {
        "ORDER_NOT_ARCHIVABLE": 409,
        "ORDER_ALREADY_ARCHIVED": 409,
        "ORDER_NOT_ARCHIVED": 409,
        "ARCHIVE_PERMISSION_DENIED": 403,
        "RESTORE_PERMISSION_DENIED": 403,
        "INVALID_ARCHIVE_REASON": 422,
    }
    return HTTPException(
        status_code=status_by_code.get(exc.code, 409),
        detail={"code": exc.code, "message": str(exc)},
    )


@router.get("/personnel-orders", response_model=PersonnelOrderListResponse)
def list_personnel_orders_route(
    status: Optional[str] = Query(default=None),
    order_type_code: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    employee_id: Optional[int] = Query(default=None, ge=1),
    org_unit_id: Optional[int] = Query(default=None, ge=1),
    q: Optional[str] = Query(default=None, max_length=200),
    record_quality: Optional[str] = Query(default="WORKING"),
    reconstruction_quality: Optional[str] = Query(default=None),
    include_closed: bool = Query(
        default=False,
        description="Include closed documents (VOIDED and archived) in the journal.",
    ),
    include_archived: bool = Query(
        default=False,
        description="Deprecated alias for include_closed (WP-PO-LC-006).",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Organization-wide personnel orders journal."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(
            list_personnel_orders,
            status=status,
            order_type_code=order_type_code,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            org_unit_id=org_unit_id,
            q=q,
            record_quality=record_quality,
            reconstruction_quality=reconstruction_quality,
            include_closed=include_closed,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get(
    "/personnel-orders/signatory-default",
    response_model=PersonnelOrderSignatoryDefaultOut,
)
def get_personnel_order_signatory_default_route(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Resolve current default signatory for personnel order header prefill."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(get_default_personnel_order_signatory)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/personnel-orders", response_model=PersonnelOrderDetailResponse, status_code=201)
def create_personnel_order_route(
    payload: PersonnelOrderCreateIn,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a personnel order in DRAFT status."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(
            create_personnel_order_draft,
            created_by=_require_user_id(user),
            order_number=payload.order_number,
            order_date=payload.order_date,
            order_type_code=payload.order_type_code,
            source_mode=payload.source_mode,
            legal_basis_article=payload.legal_basis_article,
            signed_by_employee_id=payload.signed_by_employee_id,
            signed_by_name=payload.signed_by_name,
            signed_by_position=payload.signed_by_position,
            executor_name=payload.executor_name,
            basis_summary=payload.basis_summary,
            storage_json=payload.storage_json,
            comment=payload.comment,
        )
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/personnel-orders/{order_id}", response_model=PersonnelOrderDetailResponse)
def get_personnel_order_route(
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Personnel order detail with items, texts, attachments, and linked events."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(get_personnel_order, order_id=order_id)
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/personnel-orders/{order_id}/deleted-tombstone")
def get_deleted_personnel_order_tombstone_route(
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Admin-only, read-only data retained after an order soft-delete."""
    _require_deleted_order_tombstone_access_or_403(user)
    try:
        return get_deleted_personnel_order_tombstone(order_id)
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "PERSONNEL_ORDER_TOMBSTONE_NOT_FOUND", "message": str(exc)}) from exc


@router.patch("/personnel-orders/{order_id}", response_model=PersonnelOrderDetailResponse)
def update_personnel_order_route(
    payload: PersonnelOrderUpdateIn,
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update editable personnel order header fields."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(
            update_personnel_order_draft,
            order_id=order_id,
            order_number=payload.order_number,
            order_date=payload.order_date,
            order_type_code=payload.order_type_code,
            source_mode=payload.source_mode,
            legal_basis_article=payload.legal_basis_article,
            signed_by_employee_id=payload.signed_by_employee_id,
            signed_by_name=payload.signed_by_name,
            signed_by_position=payload.signed_by_position,
            executor_name=payload.executor_name,
            basis_summary=payload.basis_summary,
            comment=payload.comment,
        )
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/personnel-orders/{order_id}/draft-deletion-preview")
def personnel_order_draft_deletion_preview_route(
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Read-only, fail-closed dependency preview for one DRAFT order."""
    try:
        require_personnel_admin_or_403(user)
        return draft_deletion.preview(order_id, scope_unit_ids=_draft_order_scope_or_403(user))
    except draft_deletion.DraftDeletionError as exc:
        raise HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.delete("/personnel-orders/{order_id}")
def delete_personnel_order_draft_route(
    payload: PersonnelOrderDraftDeleteIn,
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Atomically delete one explicitly confirmed, isolated DRAFT order."""
    try:
        require_personnel_admin_or_403(user)
        return draft_deletion.execute(order_id=order_id, actor_user_id=int(user["user_id"]), reason=payload.reason, confirmation_phrase=payload.confirmation_phrase, scope_unit_ids=_draft_order_scope_or_403(user))
    except draft_deletion.DraftDeletionError as exc:
        raise HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.delete("/personnel-orders/{order_id}/hr-head")
def delete_personnel_order_hr_head_route(
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Backward-compatible ADMIN/HR_HEAD all-status physical deletion."""
    try:
        _require_hr_head_order_delete_or_403(user)
        return draft_deletion.execute_physical_delete(order_id=order_id)
    except draft_deletion.DraftDeletionError as exc:
        raise HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/personnel-orders/{order_id}/add-item-context")
def personnel_order_add_item_context_route(order_id: int = Path(..., ge=1), user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    require_personnel_admin_or_403(user)
    from app.services.personnel_order_add_item_service import get_add_item_context
    try:
        return get_add_item_context(order_id)
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)


@router.post("/personnel-orders/{order_id}/items", response_model=PersonnelOrderDetailResponse)
def create_personnel_order_item_route(
    payload: PersonnelOrderItemCreateIn,
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Add a numbered item to an editable personnel order."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(
            create_personnel_order_item,
            order_id=order_id,
            item_type_code=payload.item_type_code,
            employee_id=payload.employee_id,
            effective_date=payload.effective_date,
            period_start=payload.period_start,
            period_end=payload.period_end,
            payload=payload.payload,
            item_number=payload.item_number,
            actor_user_id=_require_user_id(user),
            template_version_id=payload.template_version_id,
            document_subject_context=payload.document_subject_context,
        )
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.patch(
    "/personnel-orders/{order_id}/items/{item_id}",
    response_model=PersonnelOrderDetailResponse,
)
def update_personnel_order_item_route(
    payload: PersonnelOrderItemUpdateIn,
    order_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update an item on an editable personnel order."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(
            update_personnel_order_item,
            order_id=order_id,
            item_id=item_id,
            item_type_code=payload.item_type_code,
            employee_id=payload.employee_id,
            effective_date=payload.effective_date,
            period_start=payload.period_start,
            period_end=payload.period_end,
            payload=payload.payload,
            item_number=payload.item_number,
        )
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.delete(
    "/personnel-orders/{order_id}/items/{item_id}",
    response_model=PersonnelOrderDetailResponse,
)
def delete_personnel_order_item_route(
    order_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Remove one item from an editable DRAFT personnel order."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(delete_personnel_order_item, order_id=order_id, item_id=item_id)
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.put(
    "/personnel-orders/{order_id}/localized-texts/{locale}",
    response_model=PersonnelOrderDetailResponse,
)
def upsert_personnel_order_localized_text_route(
    payload: PersonnelOrderLocalizedTextUpsertIn,
    order_id: int = Path(..., ge=1),
    locale: str = Path(..., min_length=2, max_length=8),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create or update localized order text for kk/ru."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(
            upsert_personnel_order_localized_text,
            order_id=order_id,
            locale=locale,
            title=payload.title,
            preamble=payload.preamble,
            body_text=payload.body_text,
            is_authoritative=payload.is_authoritative,
        )
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post(
    "/personnel-orders/{order_id}/ready-for-signature",
    response_model=PersonnelOrderDetailResponse,
)
def mark_personnel_order_ready_for_signature_route(
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Move a DRAFT order to READY_FOR_SIGNATURE."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(mark_personnel_order_ready_for_signature, order_id=order_id)
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderReadyGateError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "READY_GATE_FAILED", "problems": exc.problems},
        )
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/personnel-orders/{order_id}/template-application/preview", response_model=PersonnelOrderTemplateApplicationPreviewOut)
def preview_personnel_order_template_application_route(order_id: int = Path(..., ge=1), user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        require_personnel_admin_or_403(user)
        return call_service(preview_template_application, order_id=order_id)
    except PersonnelOrderDeletedError as exc:
        raise _deleted_order_http(exc)
    except TemplateApplicationError as exc:
        raise HTTPException(status_code=409 if exc.conflict else 422, detail=str(exc))


@router.post("/personnel-orders/{order_id}/template-application", response_model=EditorialStateResponse)
def apply_personnel_order_template_application_route(payload: PersonnelOrderTemplateApplicationIn, order_id: int = Path(..., ge=1), user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        require_personnel_admin_or_403(user)
        return call_service(apply_template_application, order_id=order_id, actor_user_id=_require_user_id(user), expected_document_revision=payload.expected_document_revision, confirm_replace_overrides=payload.confirm_replace_overrides, confirm_reapply=payload.confirm_reapply)
    except PersonnelOrderDeletedError as exc:
        raise _deleted_order_http(exc)
    except TemplateApplicationError as exc:
        raise HTTPException(status_code=409 if exc.conflict else 422, detail=str(exc))


@router.get(
    "/personnel-orders/{order_id}/editorial",
    response_model=EditorialStateResponse,
)
def get_personnel_order_editorial_route(
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return editorial block state for a personnel order."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(get_editorial_state, order_id=order_id)
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post(
    "/personnel-orders/{order_id}/editorial/generate",
    response_model=EditorialStateResponse,
)
def generate_personnel_order_editorial_route(
    order_id: int = Path(..., ge=1),
    payload: EditorialGenerateIn = EditorialGenerateIn(),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate or regenerate editorial blocks (DRAFT only)."""
    try:
        require_personnel_admin_or_403(user)
        scope = {
            key: value
            for key, value in {
                "locale": payload.locale,
                "item_id": payload.item_id,
                "block_id": payload.block_id,
                "block_type": payload.block_type,
            }.items()
            if value is not None
        }
        return call_service(
            generate_editorial,
            order_id=order_id,
            user_id=_require_user_id(user),
            scope=scope or None,
        )
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.patch(
    "/personnel-orders/{order_id}/editorial/blocks/{block_id}",
    response_model=EditorialStateResponse,
)
def patch_personnel_order_editorial_block_route(
    payload: EditorialBlockPatchIn,
    order_id: int = Path(..., ge=1),
    block_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Patch override text on an editorial block (DRAFT only)."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(
            patch_editorial_block,
            order_id=order_id,
            block_id=block_id,
            user_id=_require_user_id(user),
            override_text=payload.override_text,
            clear_override=payload.clear_override,
            expected_revision=payload.expected_revision,
        )
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderEditorialBlockNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderEditorialConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post(
    "/personnel-orders/{order_id}/editorial/blocks/{block_id}/reset-to-generated",
    response_model=EditorialStateResponse,
)
def reset_personnel_order_editorial_block_route(
    order_id: int = Path(..., ge=1),
    block_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Clear override and restore generated text as effective (DRAFT only)."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(
            reset_block_to_generated,
            order_id=order_id,
            block_id=block_id,
            user_id=_require_user_id(user),
        )
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderEditorialBlockNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get(
    "/personnel-orders/{order_id}/acknowledgements",
    response_model=PersonnelOrderAcknowledgementListResponse,
)
def list_personnel_order_acknowledgements_route(
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        require_personnel_admin_or_403(user)
        return call_service(list_current_acknowledgements, order_id=order_id)
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/personnel-orders/{order_id}/acknowledgements")
def record_personnel_order_acknowledgement_route(
    payload: PersonnelOrderAcknowledgementRecordIn,
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        require_personnel_admin_or_403(user)
        return call_service(record_acknowledgement, order_id=order_id, employee_id=payload.employee_id,
                            acknowledged_on=payload.acknowledged_on, actor_user_id=_require_user_id(user))
    except PersonnelOrderDeletedError as exc:
        raise _deleted_order_http(exc)
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderAcknowledgementError as exc:
        raise _acknowledgement_http(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/personnel-orders/{order_id}/acknowledgements/clear")
def clear_personnel_order_acknowledgement_route(
    payload: PersonnelOrderAcknowledgementClearIn,
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        require_personnel_admin_or_403(user)
        return call_service(clear_acknowledgement, order_id=order_id, employee_id=payload.employee_id,
                            actor_user_id=_require_user_id(user))
    except PersonnelOrderDeletedError as exc:
        raise _deleted_order_http(exc)
    except PersonnelOrderAcknowledgementError as exc:
        raise _acknowledgement_http(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/personnel-orders/{order_id}/register", response_model=PersonnelOrderDetailResponse)
def register_personnel_order_route(
    payload: PersonnelOrderRegisterIn,
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Register/sign a personnel order without applying employee_events."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(
            register_personnel_order,
            order_id=order_id,
            target_status=payload.target_status,
        )
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/personnel-orders/{order_id}/apply", response_model=PersonnelOrderDetailResponse)
def apply_personnel_order_route(
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Apply a signed/registered personnel order, creating employee_events."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(
            apply_personnel_order,
            order_id=order_id,
            created_by=_require_user_id(user),
        )
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderAlreadyAppliedError as exc:
        raise _conflict_http409(exc)
    except HirePhotoNotReadyError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)})
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get(
    "/personnel-orders/{order_id}/lifecycle-audit",
    response_model=PersonnelOrderLifecycleAuditListResponse,
)
def list_personnel_order_lifecycle_audit_route(
    order_id: int = Path(..., ge=1),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Read-only lifecycle audit trail for a personnel order (WP-PO-LC-DEL-003)."""
    try:
        # Transitional: keep existing personnel admin guard until PERSONNEL_ORDERS_AUDIT_READ
        # grants are bound to contours (PO-LC-DEL-002 §6.2).
        require_personnel_admin_or_403(user)
        return call_service(
            list_personnel_order_lifecycle_audit,
            order_id=order_id,
            limit=limit,
            offset=offset,
        )
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/personnel-orders/{order_id}/document-review", response_model=PersonnelOrderDocumentReviewOut)
def get_personnel_order_document_review_route(order_id: int = Path(..., ge=1), user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        require_personnel_admin_or_403(user)
        return call_service(get_document_review, order_id=order_id)
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


def _document_review_mutation(order_id: int, payload: Any, action: str, user: Dict[str, Any]) -> Dict[str, Any]:
    require_personnel_admin_or_403(user)
    try:
        return call_service(mutate_document_review, order_id=order_id, action=action,
            expected_document_revision=payload.expected_document_revision, reason_code=payload.reason_code,
            note=payload.note, actor_user_id=_require_user_id(user))
    except PersonnelOrderDeletedError as exc:
        raise _deleted_order_http(exc)
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderDocumentReviewConflictError as exc:
        raise HTTPException(status_code=409, detail={"code": str(exc), "message": str(exc)})
    except PersonnelOrderDocumentReviewValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": "DOCUMENT_REVIEW_BLOCKED", "blockers": exc.blockers})


@router.post("/personnel-orders/{order_id}/document-review/confirm", response_model=PersonnelOrderDocumentReviewOut)
def confirm_personnel_order_document_review_route(payload: PersonnelOrderDocumentReviewConfirmIn, order_id: int = Path(..., ge=1), user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return _document_review_mutation(order_id, payload, LIFECYCLE_AUDIT_ACTION_DOCUMENT_CONFIRMED, user)


@router.post("/personnel-orders/{order_id}/document-review/reopen", response_model=PersonnelOrderDocumentReviewOut)
def reopen_personnel_order_document_review_route(payload: PersonnelOrderDocumentReviewReopenIn, order_id: int = Path(..., ge=1), user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return _document_review_mutation(order_id, payload, LIFECYCLE_AUDIT_ACTION_DOCUMENT_REOPENED, user)


@router.get("/personnel-orders/{order_id}/document-history", response_model=PersonnelOrderLifecycleAuditListResponse)
def list_personnel_order_document_history_route(order_id: int = Path(..., ge=1), user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    require_personnel_admin_or_403(user)
    result = call_service(list_personnel_order_lifecycle_audit, order_id=order_id, limit=500, offset=0)
    result["items"] = [item for item in result["items"] if item["action"] in {LIFECYCLE_AUDIT_ACTION_DOCUMENT_CONFIRMED, LIFECYCLE_AUDIT_ACTION_DOCUMENT_REOPENED, "HEADER_UPDATED"}]
    result["total"] = len(result["items"])
    return result

@router.post("/personnel-orders/header-duplicate-preview")
def personnel_order_header_duplicate_preview_route(payload: PersonnelOrderHeaderDuplicatePreviewIn, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    require_personnel_admin_or_403(user)
    return call_service(duplicate_preview, order_number=payload.order_number, order_date=payload.order_date, order_id=payload.order_id)

@router.patch("/personnel-orders/{order_id}/document-header")
def patch_personnel_order_document_header_route(payload: PersonnelOrderDocumentHeaderPatchIn, order_id: int = Path(..., ge=1), user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        require_personnel_admin_or_403(user)
        return call_service(patch_document_header, order_id=order_id, expected_document_revision=payload.expected_document_revision, order_number=payload.order_number, order_date=payload.order_date, source_title=payload.source_title, source_title_locale=payload.source_title_locale, reason_code=payload.reason_code, reason_text=payload.reason_text, actor_user_id=_require_user_id(user))
    except PersonnelOrderDeletedError as exc:
        raise _deleted_order_http(exc)
    except PersonnelOrderDuplicateError as exc:
        raise _conflict_http409(exc)
    except PersonnelOrderDocumentReviewConflictError as exc:
        raise HTTPException(status_code=409, detail={"code":str(exc)})
    except ValueError as exc:
        raise HTTPException(status_code=422 if str(exc)=="CORRECTION_REASON_REQUIRED" else 409, detail={"code":str(exc)})

@router.patch("/personnel-orders/{order_id}/document-items/{item_id}")
def patch_personnel_order_document_item_route(payload: PersonnelOrderDocumentItemPatchIn, order_id: int = Path(..., ge=1), item_id: int = Path(..., ge=1), user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        require_personnel_admin_or_403(user)
        return call_service(patch_document_item, order_id=order_id,item_id=item_id,expected_document_revision=payload.expected_document_revision,item_type_code=payload.item_type_code,employee_id=payload.employee_id,effective_date=payload.effective_date,document_subject_context=payload.document_subject_context.model_dump() if payload.document_subject_context else None,reason_code=payload.reason_code,reason_text=payload.reason_text,actor_user_id=_require_user_id(user))
    except PersonnelOrderDeletedError as exc: raise _deleted_order_http(exc)
    except PersonnelOrderDocumentReviewConflictError as exc: raise HTTPException(status_code=409,detail={"code":str(exc)})
    except ValueError as exc: raise HTTPException(status_code=422,detail={"code":str(exc)})


@router.get("/personnel-orders/{order_id}/document-items", response_model=PersonnelOrderDocumentItemListResponse)
def list_personnel_order_document_items_route(order_id: int = Path(..., ge=1), user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    require_personnel_admin_or_403(user)
    try:
        return call_service(list_document_items, order_id=order_id)
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/personnel-orders/{order_id}/cancel", response_model=PersonnelOrderDetailResponse)
def cancel_personnel_order_route(
    payload: PersonnelOrderCancelIn,
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Cancel an unregistered DRAFT/READY personnel order (WP-PO-LC-DEL-004)."""
    try:
        return call_service(
            cancel_personnel_order,
            order_id=order_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            actor_user_id=_require_user_id(user),
        )
    except PersonnelOrderDeletedError as exc:
        raise _deleted_order_http(exc)
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": str(exc)})
    except PersonnelOrderAlreadyVoidedError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "ORDER_ALREADY_VOIDED", "message": str(exc)},
        )
    except PersonnelOrderCancelError as exc:
        raise _cancel_error_http(exc)
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/personnel-orders/{order_id}/archive", response_model=PersonnelOrderDetailResponse)
def archive_personnel_order_route(
    payload: PersonnelOrderArchiveIn,
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Archive a REGISTERED/VOIDED personnel order (WP-PO-LC-DEL-005)."""
    try:
        return call_service(
            archive_personnel_order,
            order_id=order_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            actor_user_id=_require_user_id(user),
        )
    except PersonnelOrderDeletedError as exc:
        raise _deleted_order_http(exc)
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": str(exc)})
    except PersonnelOrderArchiveError as exc:
        raise _archive_error_http(exc)
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/personnel-orders/{order_id}/restore", response_model=PersonnelOrderDetailResponse)
def restore_personnel_order_route(
    payload: PersonnelOrderRestoreIn,
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Restore an archived personnel order (WP-PO-LC-DEL-005)."""
    try:
        return call_service(
            restore_personnel_order,
            order_id=order_id,
            actor_user_id=_require_user_id(user),
        )
    except PersonnelOrderDeletedError as exc:
        raise _deleted_order_http(exc)
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": str(exc)})
    except PersonnelOrderArchiveError as exc:
        raise _archive_error_http(exc)
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/personnel-orders/{order_id}/void", response_model=PersonnelOrderDetailResponse)
def void_personnel_order_route(
    payload: PersonnelOrderVoidIn,
    order_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Cancel a draft/ready order or void a signed/registered order."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(
            void_personnel_order,
            order_id=order_id,
            void_reason=payload.void_reason,
            voided_by=_require_user_id(user),
        )
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderAlreadyVoidedError as exc:
        raise _conflict_http409(exc)
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post(
    "/personnel-orders/{order_id}/items/{item_id}/void",
    response_model=PersonnelOrderDetailResponse,
)
def void_personnel_order_item_route(
    payload: PersonnelOrderVoidIn,
    order_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Void a single order item and cascade void linked employee_events."""
    try:
        require_personnel_admin_or_403(user)
        return call_service(
            void_personnel_order_item,
            order_id=order_id,
            item_id=item_id,
            void_reason=payload.void_reason,
            voided_by=_require_user_id(user),
        )
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelOrderAlreadyVoidedError as exc:
        raise _conflict_http409(exc)
    except PersonnelOrderItemAlreadyVoidedError as exc:
        raise _conflict_http409(exc)
    except PersonnelOrderVoidChainError as exc:
        raise _conflict_http409(exc)
    except PersonnelOrderArchivedError as exc:
        raise _order_archived_http(exc)
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)
