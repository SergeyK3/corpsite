from fastapi import APIRouter,Depends,HTTPException,Query
from app.auth import get_current_user
from app.db.engine import engine
from app.directory.rbac import compute_scope,require_personnel_visibility_or_403
from app.security.admin_permissions import PPR_MIGRATION_STATUS_READ_PERMISSION,has_admin_permission
from app.services.ppr_migration_status_report_service import list_universes,matrix,person_cells
router=APIRouter(prefix='/directory/personnel/migration-status',tags=['ppr-migration-status'])
def _scope(user):
    if not has_admin_permission(int(user['user_id']),PPR_MIGRATION_STATUS_READ_PERMISSION):raise HTTPException(403,detail={'code':'PPR_MIGRATION_STATUS_READ_REQUIRED'})
    s=compute_scope(int(user['user_id']),user,include_inactive=False);require_personnel_visibility_or_403(user,s);return s
@router.get('/universes')
def universes(user:dict=Depends(get_current_user)):
    with engine.connect() as c:return {'items':list_universes(c,_scope(user))}
@router.get('/persons/{person_id}')
def person_status(person_id:int,universe_id:int=Query(...,ge=1),user:dict=Depends(get_current_user)):
    with engine.connect() as c:r=person_cells(c,universe_id=universe_id,person_id=person_id,scope=_scope(user))
    if r is None:raise HTTPException(404,detail={'code':'MIGRATION_STATUS_PERSON_NOT_FOUND'})
    return r
@router.get('')
def report(universe_id:int=Query(...,ge=1),page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=100),section:str|None=None,status:str|None=None,reason:str|None=None,org_unit_id:int|None=Query(None,ge=1),q:str|None=None,user:dict=Depends(get_current_user)):
    try:
        with engine.connect() as c:r=matrix(c,universe_id=universe_id,scope=_scope(user),page=page,page_size=page_size,section=section,status=status,reason=reason,org_unit_id=org_unit_id,q=q)
    except ValueError:raise HTTPException(422,detail={'code':'INVALID_MIGRATION_STATUS_FILTER'})
    if r is None:raise HTTPException(404,detail={'code':'MIGRATION_STATUS_UNIVERSE_NOT_FOUND'})
    return r
