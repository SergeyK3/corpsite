from fastapi import APIRouter,Depends,HTTPException
from app.auth import get_current_user
from app.db.engine import engine
from sqlalchemy import text
from app.directory.rbac import compute_scope,require_personnel_visibility_or_403
from app.security.ppr_stage1_permissions import require_ppr_stage1_general_manage
from app.api.ppr_stage1_general_schemas import Stage1PreviewRequest,Stage1RunRequest,Stage1RunOut
from app.services.ppr_stage1_general_service import Stage1Error,Stage1NotFoundError,Stage1ConflictError,preview_stage1,get_stage1_run,approve_stage1,execute_next_stage1,accept_stage1_run
router=APIRouter(prefix='/personnel/ppr-migration/stage-1',tags=['ppr-stage-1'])
def _actor(user:dict)->tuple[int,dict]:
    actor=require_ppr_stage1_general_manage(user); scope=compute_scope(actor,user,include_inactive=False); require_personnel_visibility_or_403(user,scope); return actor,scope
def _scope_run(c,cohort_id:int,scope:dict)->None:
    if scope.get('privileged') or scope.get('scope_unit_ids') is None:return
    allowed={int(v) for v in scope.get('scope_unit_ids',[])}
    units=c.execute(text("SELECT e.org_unit_id FROM public.ppr_stage0_cohort_participants p JOIN public.employees e ON e.employee_id=p.employee_id WHERE p.stage0_cohort_run_id=:id"),{'id':cohort_id}).scalars().all()
    if not units or any(u is None or int(u) not in allowed for u in units):raise HTTPException(404,detail={'code':'STAGE1_RUN_OUT_OF_SCOPE','message':'Данные этого этапа находятся вне разрешённого для вас подразделения.'})
def _scope_stage1(c,run_id:int,scope:dict)->None:
    cohort=c.execute(text('SELECT stage0_cohort_run_id FROM public.ppr_stage1_general_runs WHERE stage1_run_id=:id'),{'id':run_id}).scalar_one_or_none()
    if cohort is None:raise HTTPException(404,detail={'code':'STAGE1_RUN_NOT_FOUND','message':'Stage 1 run not found.'})
    _scope_run(c,int(cohort),scope)
def _error(e:Stage1Error)->HTTPException: return HTTPException(404 if isinstance(e,Stage1NotFoundError) else 409 if isinstance(e,Stage1ConflictError) else 422,detail={'code':e.code,'message':str(e)})
@router.post('/preview',response_model=Stage1RunOut)
def preview(payload:Stage1PreviewRequest,user:dict=Depends(get_current_user)):
    try:
        actor,scope=_actor(user)
        with engine.begin() as c:
            _scope_run(c,payload.stage0_cohort_run_id,scope); return preview_stage1(c,stage0_cohort_run_id=payload.stage0_cohort_run_id,actor_user_id=actor)
    except Stage1Error as e: raise _error(e)
@router.get('/runs/{run_id}',response_model=Stage1RunOut)
def get_run(run_id:int,user:dict=Depends(get_current_user)):
    _,scope=_actor(user)
    try:
        with engine.connect() as c:_scope_stage1(c,run_id,scope); return get_stage1_run(c,run_id=run_id)
    except Stage1Error as e: raise _error(e)
@router.post('/approve',response_model=Stage1RunOut)
def approve(payload:Stage1RunRequest,user:dict=Depends(get_current_user)):
    _,scope=_actor(user)
    try:
        with engine.begin() as c:_scope_stage1(c,payload.stage1_run_id,scope); return approve_stage1(c,run_id=payload.stage1_run_id)
    except Stage1Error as e: raise _error(e)
@router.post('/execute-next',response_model=Stage1RunOut)
def execute_next(payload:Stage1RunRequest,user:dict=Depends(get_current_user)):
    _,scope=_actor(user)
    try:
        with engine.begin() as c:_scope_stage1(c,payload.stage1_run_id,scope); return execute_next_stage1(c,run_id=payload.stage1_run_id)
    except Stage1Error as e: raise _error(e)
@router.post('/accept',response_model=Stage1RunOut)
def accept(payload:Stage1RunRequest,user:dict=Depends(get_current_user)):
    actor,scope=_actor(user)
    try:
        with engine.connect().execution_options(isolation_level='SERIALIZABLE') as c:
            with c.begin():_scope_stage1(c,payload.stage1_run_id,scope); return accept_stage1_run(c,run_id=payload.stage1_run_id,actor_user_id=actor)
    except Stage1Error as e: raise _error(e)
