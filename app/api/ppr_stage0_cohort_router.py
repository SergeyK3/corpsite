"""PPR Stage 0 PREVIEW/FREEZE routes."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import text

from app.api.ppr_stage0_cohort_schemas import Stage0BlockerListOut, Stage0FreezeOut, Stage0FreezeRequest, Stage0PreviewOut, Stage0PreviewRequest, Stage0RunOut, Stage0SourceBatchListOut
from app.auth import get_current_user
from app.db.engine import engine
from app.directory.rbac import compute_scope, require_personnel_visibility_or_403
from app.security.ppr_stage0_permissions import require_ppr_stage0_cohort_manage
from app.services.ppr_stage0_cohort_service import Stage0ConflictError, Stage0Error, Stage0NotFoundError, Stage0ValidationError, freeze_stage0_cohort, get_stage0_blockers, get_stage0_run, list_stage0_source_batches, preview_stage0_cohort

router = APIRouter(prefix="/personnel/ppr-migration/stage-0", tags=["ppr-stage-0"])

def _scope(user: dict[str, Any], actor: int) -> dict[str, Any]:
    scope = compute_scope(actor, user, include_inactive=False)
    require_personnel_visibility_or_403(user, scope)
    return scope

def _error(exc: Stage0Error) -> HTTPException:
    if isinstance(exc, Stage0NotFoundError): return HTTPException(404, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, Stage0ConflictError): return HTTPException(409, detail={"code": exc.code, "message": str(exc)})
    return HTTPException(422, detail={"code": exc.code, "message": str(exc)})

@router.post("/preview", response_model=Stage0PreviewOut)
def preview(payload: Stage0PreviewRequest, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    actor = require_ppr_stage0_cohort_manage(user); scope = _scope(user, actor)
    try:
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
            with conn.begin():
                conn.execute(text("SET TRANSACTION READ ONLY"))
                return preview_stage0_cohort(conn, source_batch_id=payload.source_batch_id, supplemental_of_run_id=payload.supplemental_of_run_id, scope=scope, include_correction_details=payload.correction_details)
    except Stage0Error as exc: raise _error(exc)

@router.get("/source-batches", response_model=Stage0SourceBatchListOut)
def list_source_batches(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    actor = require_ppr_stage0_cohort_manage(user); _scope(user, actor)
    with engine.connect() as conn:
        return {"items": list_stage0_source_batches(conn)}

@router.post("/freeze", response_model=Stage0FreezeOut)
def freeze(payload: Stage0FreezeRequest, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    actor = require_ppr_stage0_cohort_manage(user); scope = _scope(user, actor)
    try:
        with engine.connect().execution_options(isolation_level="SERIALIZABLE") as conn:
            with conn.begin():
                return freeze_stage0_cohort(conn, source_batch_id=payload.source_batch_id, preview_fingerprint=payload.preview_fingerprint, actor_user_id=actor, supplemental_of_run_id=payload.supplemental_of_run_id, scope=scope)
    except Stage0Error as exc: raise _error(exc)

@router.get("/runs/{run_id}", response_model=Stage0RunOut)
def get_run(run_id: int = Path(ge=1), correction_details: bool = Query(default=False), user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    actor = require_ppr_stage0_cohort_manage(user); scope = _scope(user, actor)
    try:
        with engine.connect() as conn: return get_stage0_run(conn, run_id=run_id, scope=scope, include_correction_details=correction_details)
    except Stage0Error as exc: raise _error(exc)

@router.get("/runs/{run_id}/blockers", response_model=Stage0BlockerListOut)
def get_blockers(run_id: int = Path(ge=1), user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    actor = require_ppr_stage0_cohort_manage(user); scope = _scope(user, actor)
    try:
        with engine.connect() as conn:
            get_stage0_run(conn, run_id=run_id, scope=scope)
            return {"items": get_stage0_blockers(conn, run_id=run_id)}
    except Stage0Error as exc: raise _error(exc)
