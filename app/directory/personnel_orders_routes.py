# FILE: app/directory/personnel_orders_routes.py
"""Personnel orders API: read (WP-PO-004A), draft/register (WP-PO-004B), apply (WP-PO-004C), void (WP-PO-004D)."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.auth import get_current_user
from app.directory.common import as_http500, call_service
from app.directory.personnel_orders_schemas import (
    EditorialBlockPatchIn,
    EditorialGenerateIn,
    EditorialStateResponse,
    PersonnelOrderCreateIn,
    PersonnelOrderDetailResponse,
    PersonnelOrderItemCreateIn,
    PersonnelOrderItemUpdateIn,
    PersonnelOrderLifecycleAuditListResponse,
    PersonnelOrderListResponse,
    PersonnelOrderLocalizedTextUpsertIn,
    PersonnelOrderRegisterIn,
    PersonnelOrderUpdateIn,
    PersonnelOrderVoidIn,
)
from app.directory.rbac import require_personnel_admin_or_403
from app.services.personnel_orders_apply_service import (
    PersonnelOrderAlreadyAppliedError,
    apply_personnel_order,
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
    PersonnelOrderItemNotFoundError,
    create_personnel_order_draft,
    create_personnel_order_item,
    mark_personnel_order_ready_for_signature,
    register_personnel_order,
    update_personnel_order_draft,
    update_personnel_order_item,
    upsert_personnel_order_localized_text,
)
from app.services.personnel_orders_editorial_service import (
    PersonnelOrderEditorialBlockNotFoundError,
    PersonnelOrderEditorialConflictError,
    PersonnelOrderReadyGateError,
    generate_editorial,
    get_editorial_state,
    patch_editorial_block,
    reset_block_to_generated,
)
from app.services.personnel_orders_query_service import (
    PersonnelOrderNotFoundError,
    PersonnelOrderValidationError,
    get_personnel_order,
    list_personnel_orders,
    validation_error_to_http422,
)
from app.services.personnel_order_lifecycle_audit_service import (
    list_personnel_order_lifecycle_audit,
)

router = APIRouter()


def _require_user_id(user: Dict[str, Any]) -> int:
    uid = user.get("user_id") or user.get("id")
    if uid is None:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return int(uid)


def _conflict_http409(exc: PersonnelOrderConflictError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.get("/personnel-orders", response_model=PersonnelOrderListResponse)
def list_personnel_orders_route(
    status: Optional[str] = Query(default=None),
    order_type_code: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    employee_id: Optional[int] = Query(default=None, ge=1),
    org_unit_id: Optional[int] = Query(default=None, ge=1),
    q: Optional[str] = Query(default=None, max_length=200),
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
            limit=limit,
            offset=offset,
        )
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
            comment=payload.comment,
        )
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
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


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
        )
    except PersonnelOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
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
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
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
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


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
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
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
    except PersonnelOrderValidationError as exc:
        raise validation_error_to_http422(exc)
    except PersonnelOrderConflictError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)
