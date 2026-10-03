from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.auth import get_current_user
from app.security.admin_permissions import has_technical_personnel_order_cleanup_permission
from app.services import technical_personnel_order_cleanup_service as service

router = APIRouter(prefix="/technical-personnel-order-cleanup", tags=["technical-personnel-order-cleanup"])

def _require(user: dict[str, Any]) -> int:
    uid = int(user["user_id"])
    if not has_technical_personnel_order_cleanup_permission(uid):
        raise HTTPException(403, detail={"code": "TECHNICAL_ORDER_CLEANUP_PERMISSION_REQUIRED"})
    return uid

def _error(exc: service.TechnicalOrderCleanupError) -> HTTPException:
    return HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message})

class ExecuteIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    confirmation_phrase: str = Field(min_length=1, max_length=200)

class BatchIn(ExecuteIn):
    order_ids: list[int] = Field(min_length=1, max_length=25)

class BatchPreviewIn(BaseModel):
    order_ids: list[int] = Field(min_length=1, max_length=25)

@router.get("/search")
def search(order_id: int | None = Query(None, ge=1), q: str | None = None, employee_name: str | None = None, import_source: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(25), user: dict[str, Any] = Depends(get_current_user)):
    _require(user)
    try: return service.search(order_id=order_id, q=q, employee_name=employee_name, import_source=import_source, page=page, page_size=page_size)
    except service.TechnicalOrderCleanupError as exc: raise _error(exc) from exc

@router.post("/batch-preview")
def batch_preview(body: BatchPreviewIn, user: dict[str, Any] = Depends(get_current_user)):
    _require(user)
    try: return service.batch_preview(order_ids=body.order_ids)
    except service.TechnicalOrderCleanupError as exc: raise _error(exc) from exc

@router.post("/batch-execute")
def batch_execute(body: BatchIn, user: dict[str, Any] = Depends(get_current_user)):
    actor = _require(user)
    try: return service.batch_execute(order_ids=body.order_ids, actor_user_id=actor, reason=body.reason, confirmation_phrase=body.confirmation_phrase)
    except service.TechnicalOrderCleanupError as exc: raise _error(exc) from exc

@router.get("/{order_id}/preview")
def preview(order_id: int, user: dict[str, Any] = Depends(get_current_user)):
    _require(user)
    try: return service.preview(order_id)
    except service.TechnicalOrderCleanupError as exc: raise _error(exc) from exc

@router.get("/{order_id}/provenance-preview")
def provenance_preview(order_id: int, user: dict[str, Any] = Depends(get_current_user)):
    _require(user)
    try: return service.confirm_provenance_preview(order_id)
    except service.TechnicalOrderCleanupError as exc: raise _error(exc) from exc

@router.post("/{order_id}/confirm-provenance")
def confirm_provenance(order_id: int, body: ExecuteIn, user: dict[str, Any] = Depends(get_current_user)):
    actor = _require(user)
    try: return service.confirm_provenance(order_id=order_id, actor_user_id=actor, reason=body.reason, confirmation_phrase=body.confirmation_phrase)
    except service.TechnicalOrderCleanupError as exc: raise _error(exc) from exc

@router.post("/{order_id}/execute")
def execute(order_id: int, body: ExecuteIn, user: dict[str, Any] = Depends(get_current_user)):
    actor = _require(user)
    try: return service.execute(order_id=order_id, actor_user_id=actor, reason=body.reason, confirmation_phrase=body.confirmation_phrase)
    except service.TechnicalOrderCleanupError as exc: raise _error(exc) from exc
