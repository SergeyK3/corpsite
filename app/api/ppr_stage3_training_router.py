"""Protected Stage 3 training API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from app.auth import get_current_user
from app.db.engine import engine
from app.control_list_projection.service import organization_timezone
from app.directory.rbac import compute_scope, require_personnel_visibility_or_403
from app.security.ppr_stage3_permissions import require_ppr_stage3_training_manage
from app.api.ppr_stage3_training_schemas import Stage3PreviewRequest,Stage3CreateRunRequest,Stage3SkipRequest,Stage3CancelRequest,Stage3AcceptRequest
from app.services import ppr_stage3_training_service as service

router=APIRouter(prefix="/personnel/ppr-migration/stage-3/training",tags=["ppr-stage-3"])

def _error(exc:service.Stage3Error)->HTTPException:
    code = str(exc).strip() or exc.code
    return HTTPException(404 if isinstance(exc,service.Stage3NotFoundError) else 409,detail={"code":code,"message":code})
def _actor(user:dict)->tuple[int,dict]:
    actor=require_ppr_stage3_training_manage(user)
    scope=compute_scope(actor,user,include_inactive=False)
    require_personnel_visibility_or_403(user,scope)
    return actor,scope
def _scope_cohort(conn,cohort_id:int,scope:dict)->None:
    if scope.get("privileged") is True:return
    if "scope_unit_ids" not in scope:
        raise HTTPException(403,detail={"code":"STAGE3_SCOPE_UNRESOLVED","message":"Недостаточно данных для проверки области доступа."})
    if scope["scope_unit_ids"] is None:return
    allowed={int(x) for x in scope.get("scope_unit_ids",[])}
    units=conn.execute(text("""SELECT e.org_unit_id FROM public.ppr_stage0_cohort_participants p JOIN public.employees e ON e.employee_id=p.employee_id WHERE p.stage0_cohort_run_id=:id"""),{"id":cohort_id}).scalars().all()
    if not units or any(x is None or int(x) not in allowed for x in units):
        raise HTTPException(403,detail={"code":"STAGE3_COHORT_OUT_OF_SCOPE","message":"Прогон недоступен в вашем подразделении."})
def _scope_run(conn,run_id:int,scope:dict)->None:
    cohort=conn.execute(text("SELECT stage0_cohort_run_id FROM public.ppr_stage_runs WHERE stage_run_id=:id AND stage_code='training'"),{"id":run_id}).scalar_one_or_none()
    if cohort is None: raise service.Stage3NotFoundError("STAGE3_RUN_NOT_FOUND")
    _scope_cohort(conn,int(cohort),scope)
def _out(value:dict, user:dict)->dict:
    timezone,_=organization_timezone()
    return {**service.redact_stage3_dto(value,user=user),"organization_timezone":timezone}

def _require_preview_enabled() -> None:
    if not service.ppr_stage3_training_preview_enabled():
        raise service.Stage3ValidationError("STAGE3_PREVIEW_DISABLED")

def _require_execution_enabled() -> None:
    if not service.ppr_stage3_training_execution_enabled():
        raise service.Stage3ValidationError("STAGE3_EXECUTION_DISABLED")

def _require_accept_enabled() -> None:
    if not service.ppr_stage3_training_accept_enabled():
        raise service.Stage3ValidationError("STAGE3_ACCEPT_DISABLED")

@router.post("/preview")
def preview(payload:Stage3PreviewRequest,user:dict=Depends(get_current_user)):
    try:
        _require_preview_enabled()
        actor,scope=_actor(user)
        # Compute cannot persist an envelope, PMF draft or canonical record.
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
            with conn.begin():
                conn.execute(text("SET TRANSACTION READ ONLY"))
                _scope_cohort(conn,payload.stage0_cohort_run_id,scope)
                computed=service.compute_preview_stage3(conn,stage0_cohort_run_id=payload.stage0_cohort_run_id)
        return _out(computed,user)
    except service.Stage3Error as exc: raise _error(exc)
@router.post("/runs")
def create_run(payload:Stage3CreateRunRequest,user:dict=Depends(get_current_user)):
    try:
        _require_preview_enabled()
        actor,scope=_actor(user)
        with engine.connect().execution_options(isolation_level="SERIALIZABLE") as conn:
            with conn.begin():
                _scope_cohort(conn,payload.stage0_cohort_run_id,scope)
                return _out(service.persist_preview_stage3(conn,stage0_cohort_run_id=payload.stage0_cohort_run_id,actor_user_id=actor,expected_preview_fingerprint=payload.preview_fingerprint),user)
    except service.Stage3Error as exc: raise _error(exc)

@router.get("/runs/{run_id}")
def get_run(run_id:int,user:dict=Depends(get_current_user)):
    try:
        _require_preview_enabled()
        _,scope=_actor(user)
        with engine.connect() as conn:
            _scope_run(conn,run_id,scope); return _out(service.redacted_view_run_stage3(conn,run_id=run_id,user=user),user)
    except service.Stage3Error as exc: raise _error(exc)
@router.post("/runs/{run_id}/approve")
def approve(run_id:int,user:dict=Depends(get_current_user)):
    try:
        _require_preview_enabled()
        actor,scope=_actor(user)
        with engine.begin() as conn:
            _scope_run(conn,run_id,scope); return _out(service.approve_stage3(conn,run_id=run_id,actor_user_id=actor),user)
    except service.Stage3Error as exc: raise _error(exc)
@router.post("/runs/{run_id}/execute-next")
def execute(run_id:int,user:dict=Depends(get_current_user)):
    try:
        _require_execution_enabled()
        actor,scope=_actor(user)
        with engine.begin() as conn:
            _scope_run(conn,run_id,scope); return _out(service.execute_next_stage3(conn,run_id=run_id,actor_user_id=actor),user)
    except service.Stage3Error as exc: raise _error(exc)
@router.post("/runs/{run_id}/resume")
def resume(run_id:int,user:dict=Depends(get_current_user)):
    try:
        _require_execution_enabled()
        actor,scope=_actor(user)
        with engine.begin() as conn:
            _scope_run(conn,run_id,scope); return _out(service.execute_next_stage3(conn,run_id=run_id,actor_user_id=actor,resume=True),user)
    except service.Stage3Error as exc: raise _error(exc)
@router.post("/runs/{run_id}/participants/{participant_id}/skip")
def skip(run_id:int,participant_id:int,payload:Stage3SkipRequest,user:dict=Depends(get_current_user)):
    try:
        _require_preview_enabled()
        actor,scope=_actor(user)
        with engine.begin() as conn:
            _scope_run(conn,run_id,scope); return _out(service.skip_stage3_participant(conn,run_id=run_id,participant_id=participant_id,actor_user_id=actor,reason=payload.reason),user)
    except service.Stage3Error as exc: raise _error(exc)
@router.post("/runs/{run_id}/cancel")
def cancel(run_id:int,payload:Stage3CancelRequest,user:dict=Depends(get_current_user)):
    try:
        _require_preview_enabled()
        actor,scope=_actor(user)
        with engine.begin() as conn:
            _scope_run(conn,run_id,scope); return _out(service.cancel_stage3(conn,run_id=run_id,actor_user_id=actor,reason=payload.reason),user)
    except service.Stage3Error as exc: raise _error(exc)
@router.get("/runs/{run_id}/acceptance-summary")
def summary(run_id:int,user:dict=Depends(get_current_user)):
    try:
        _require_accept_enabled()
        _,scope=_actor(user)
        with engine.connect() as conn:
            _scope_run(conn,run_id,scope); return _out(service.acceptance_summary(conn,run_id=run_id),user)
    except service.Stage3Error as exc: raise _error(exc)
@router.post("/runs/{run_id}/accept")
def accept(run_id:int,payload:Stage3AcceptRequest,user:dict=Depends(get_current_user)):
    actor,scope=_actor(user)
    try:
        _require_accept_enabled()
        with engine.connect().execution_options(isolation_level="SERIALIZABLE") as conn:
            with conn.begin():
                _scope_run(conn,run_id,scope)
                return _out(service.accept_stage3(conn,run_id=run_id,actor_user_id=actor,acceptance_fingerprint=payload.acceptance_fingerprint),user)
    except service.Stage3Error as exc: raise _error(exc)
    except Exception as exc:
        # The acceptance UoW has already rolled back.  Persist a pause only in
        # this separate, conditional transaction; a concurrent cancel/accept
        # wins without being overwritten.
        try:
            with engine.begin() as pause_conn:
                _scope_run(pause_conn,run_id,scope)
                service.pause_acceptance_after_rollback(pause_conn,run_id=run_id,exc=exc)
        except Exception:
            # Do not claim a pause if the separate operational write fails.
            pass
        raise HTTPException(409,detail={"code":"STAGE3_ACCEPTANCE_PAUSED","message":"РџСЂРёРЅСЏС‚РёРµ РѕСЃС‚Р°РЅРѕРІР»РµРЅРѕ; РїРѕРІС‚РѕСЂРёС‚Рµ РїСЂРёРЅСЏС‚РёРµ."})
@router.post("/runs/{run_id}/retry-accept")
def retry_accept(run_id:int,payload:Stage3AcceptRequest,user:dict=Depends(get_current_user)):
    return accept(run_id,payload,user)
