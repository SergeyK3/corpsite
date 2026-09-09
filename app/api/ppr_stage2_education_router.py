"""Protected Stage 2 education API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from app.auth import get_current_user
from app.db.engine import engine
from app.control_list_projection.service import organization_timezone
from app.directory.rbac import compute_scope, require_personnel_visibility_or_403
from app.security.ppr_stage2_permissions import require_ppr_stage2_education_manage
from app.api.ppr_stage2_education_schemas import Stage2PreviewRequest,Stage2RunRequest,Stage2SkipRequest,Stage2CancelRequest,Stage2AcceptRequest
from app.services import ppr_stage2_education_service as service

router=APIRouter(prefix="/personnel/ppr-migration/stage-2/education",tags=["ppr-stage-2"])

def _error(exc:service.Stage2Error)->HTTPException:
    code = str(exc).strip() or exc.code
    return HTTPException(404 if isinstance(exc,service.Stage2NotFoundError) else 409,detail={"code":code,"message":code})
def _actor(user:dict)->tuple[int,dict]:
    actor=require_ppr_stage2_education_manage(user)
    scope=compute_scope(actor,user,include_inactive=False)
    require_personnel_visibility_or_403(user,scope)
    return actor,scope
def _scope_cohort(conn,cohort_id:int,scope:dict)->None:
    if scope.get("privileged") or scope.get("scope_unit_ids") is None:return
    allowed={int(x) for x in scope.get("scope_unit_ids",[])}
    units=conn.execute(text("""SELECT e.org_unit_id FROM public.ppr_stage0_cohort_participants p JOIN public.employees e ON e.employee_id=p.employee_id WHERE p.stage0_cohort_run_id=:id"""),{"id":cohort_id}).scalars().all()
    if not units or any(x is None or int(x) not in allowed for x in units):
        raise HTTPException(403,detail={"code":"STAGE2_COHORT_OUT_OF_SCOPE","message":"Прогон недоступен в вашем подразделении."})
def _scope_run(conn,run_id:int,scope:dict)->None:
    cohort=conn.execute(text("SELECT stage0_cohort_run_id FROM public.ppr_stage_runs WHERE stage_run_id=:id"),{"id":run_id}).scalar_one_or_none()
    if cohort is None: raise service.Stage2NotFoundError("STAGE2_RUN_NOT_FOUND")
    _scope_cohort(conn,int(cohort),scope)
def _out(value:dict)->dict:
    timezone,_=organization_timezone()
    return {**value,"organization_timezone":timezone}

@router.post("/preview")
def preview(payload:Stage2PreviewRequest,user:dict=Depends(get_current_user)):
    try:
        actor,scope=_actor(user)
        # Compute cannot persist an envelope, PMF draft or canonical record.
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
            with conn.begin():
                conn.execute(text("SET TRANSACTION READ ONLY"))
                _scope_cohort(conn,payload.stage0_cohort_run_id,scope)
                computed=service.compute_preview_stage2(conn,stage0_cohort_run_id=payload.stage0_cohort_run_id)
        # Freeze the verified preview only after serializable re-computation.
        with engine.connect().execution_options(isolation_level="SERIALIZABLE") as conn:
            with conn.begin():
                _scope_cohort(conn,payload.stage0_cohort_run_id,scope)
                result=service.persist_preview_stage2(conn,stage0_cohort_run_id=payload.stage0_cohort_run_id,actor_user_id=actor,expected_preview_fingerprint=computed["preview_fingerprint"])
                return _out(result)
    except service.Stage2Error as exc: raise _error(exc)
@router.get("/runs/{run_id}")
def get_run(run_id:int,user:dict=Depends(get_current_user)):
    try:
        _,scope=_actor(user)
        with engine.connect() as conn:
            _scope_run(conn,run_id,scope); return _out(service._view_run(conn,run_id))
    except service.Stage2Error as exc: raise _error(exc)
@router.post("/runs/{run_id}/approve")
def approve(run_id:int,user:dict=Depends(get_current_user)):
    try:
        actor,scope=_actor(user)
        with engine.begin() as conn:
            _scope_run(conn,run_id,scope); return _out(service.approve_stage2(conn,run_id=run_id,actor_user_id=actor))
    except service.Stage2Error as exc: raise _error(exc)
@router.post("/runs/{run_id}/execute-next")
def execute(run_id:int,user:dict=Depends(get_current_user)):
    try:
        actor,scope=_actor(user)
        with engine.begin() as conn:
            _scope_run(conn,run_id,scope); return _out(service.execute_next_stage2(conn,run_id=run_id,actor_user_id=actor))
    except service.Stage2Error as exc: raise _error(exc)
@router.post("/runs/{run_id}/resume")
def resume(run_id:int,user:dict=Depends(get_current_user)):
    try:
        actor,scope=_actor(user)
        with engine.begin() as conn:
            _scope_run(conn,run_id,scope); return _out(service.execute_next_stage2(conn,run_id=run_id,actor_user_id=actor,resume=True))
    except service.Stage2Error as exc: raise _error(exc)
@router.post("/runs/{run_id}/participants/{participant_id}/skip")
def skip(run_id:int,participant_id:int,payload:Stage2SkipRequest,user:dict=Depends(get_current_user)):
    try:
        actor,scope=_actor(user)
        with engine.begin() as conn:
            _scope_run(conn,run_id,scope); return _out(service.skip_stage2_participant(conn,run_id=run_id,participant_id=participant_id,actor_user_id=actor,reason=payload.reason))
    except service.Stage2Error as exc: raise _error(exc)
@router.post("/runs/{run_id}/cancel")
def cancel(run_id:int,payload:Stage2CancelRequest,user:dict=Depends(get_current_user)):
    try:
        actor,scope=_actor(user)
        with engine.begin() as conn:
            _scope_run(conn,run_id,scope); return _out(service.cancel_stage2(conn,run_id=run_id,actor_user_id=actor,reason=payload.reason))
    except service.Stage2Error as exc: raise _error(exc)
@router.get("/runs/{run_id}/acceptance-summary")
def summary(run_id:int,user:dict=Depends(get_current_user)):
    try:
        _,scope=_actor(user)
        with engine.connect() as conn:
            _scope_run(conn,run_id,scope); return service.acceptance_summary(conn,run_id=run_id)
    except service.Stage2Error as exc: raise _error(exc)
@router.post("/runs/{run_id}/accept")
def accept(run_id:int,payload:Stage2AcceptRequest,user:dict=Depends(get_current_user)):
    actor,scope=_actor(user)
    try:
        with engine.connect().execution_options(isolation_level="SERIALIZABLE") as conn:
            with conn.begin():
                _scope_run(conn,run_id,scope)
                return _out(service.accept_stage2(conn,run_id=run_id,actor_user_id=actor,acceptance_fingerprint=payload.acceptance_fingerprint))
    except service.Stage2Error as exc: raise _error(exc)
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
        raise HTTPException(409,detail={"code":"STAGE2_ACCEPTANCE_PAUSED","message":"РџСЂРёРЅСЏС‚РёРµ РѕСЃС‚Р°РЅРѕРІР»РµРЅРѕ; РїРѕРІС‚РѕСЂРёС‚Рµ РїСЂРёРЅСЏС‚РёРµ."})
@router.post("/runs/{run_id}/retry-accept")
def retry_accept(run_id:int,payload:Stage2AcceptRequest,user:dict=Depends(get_current_user)):
    return accept(run_id,payload,user)
