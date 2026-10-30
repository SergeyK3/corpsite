from fastapi import APIRouter,Depends,Query,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from app.auth import get_current_user
from app.directory.rbac import require_privileged_or_403
from app.services.education_program_kinds_service import list_entries,save_entry

router=APIRouter(prefix='/api/ppr/education-program-kinds',tags=['education-reference'])

class Value(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name_ru:str=Field(min_length=1,max_length=500)
    name_kk:str=Field(min_length=1,max_length=500)
    sort_order:int=0
    is_active:bool=True

class Create(Value):
    code:str=Field(min_length=1,max_length=64)

class Edit(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision:int=Field(ge=1)
    name_ru:str|None=Field(default=None,min_length=1,max_length=500)
    name_kk:str|None=Field(default=None,min_length=1,max_length=500)
    sort_order:int|None=None
    is_active:bool|None=None

@router.get('')
def read(state:Literal['all','active','inactive']='all',q:str=Query(default='',max_length=500),user:dict=Depends(get_current_user)):
    can_manage=True
    try: require_privileged_or_403(user)
    except HTTPException as exc:
        if exc.status_code!=403: raise
        can_manage=False
    return {**list_entries(state=state,q=q), 'can_manage':can_manage}

@router.post('',status_code=201)
def create(body:Create,user:dict=Depends(get_current_user)):
    require_privileged_or_403(user)
    return save_entry(**body.model_dump(),actor_user_id=int(user['user_id']))

@router.patch('/{code}')
def edit(code:str,body:Edit,user:dict=Depends(get_current_user)):
    require_privileged_or_403(user)
    return save_entry(code=code,**body.model_dump(),actor_user_id=int(user['user_id']))
