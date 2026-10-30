from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from app.auth import get_current_user
from app.directory.rbac import require_privileged_or_403
from app.services.education_document_references_service import list_values,save_value,selection_value

router=APIRouter(tags=['education-document-references'])

class Values(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name_ru:str=Field(min_length=1,max_length=500)
    name_kk:str=Field(min_length=1,max_length=500)
    is_active:bool=True
    sort_order:int=0
    description_ru:str|None=Field(default=None,max_length=2000)
    description_kk:str|None=Field(default=None,max_length=2000)

class Create(Values):
    code:str=Field(min_length=1,max_length=64)

class Edit(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision:int=Field(ge=1)
    name_ru:str=Field(default=None,min_length=1,max_length=500)
    name_kk:str=Field(default=None,min_length=1,max_length=500)
    is_active:bool=Field(default=None)
    sort_order:int=Field(default=None)
    description_ru:str|None=Field(default=None,max_length=2000)
    description_kk:str|None=Field(default=None,max_length=2000)

def register(kind,path):
    def read(state:Literal['all','active','inactive']='all',q:str=Query(default='',max_length=500),user:dict=Depends(get_current_user)):
        can_manage=True
        try:require_privileged_or_403(user)
        except HTTPException as exc:
            if exc.status_code!=403:raise
            can_manage=False
        return {**list_values(kind,state=state,q=q),'can_manage':can_manage}
    def create(body:Create,user:dict=Depends(get_current_user)):
        require_privileged_or_403(user)
        return save_value(kind,**body.model_dump(exclude_none=True),actor_user_id=int(user['user_id']))
    def edit(code:str,body:Edit,user:dict=Depends(get_current_user)):
        require_privileged_or_403(user)
        return save_value(kind,code=code,**body.model_dump(exclude_unset=True),actor_user_id=int(user['user_id']))
    def selection(code:str|None=None,locale:Literal['ru','kk']='ru',user:dict=Depends(get_current_user)):
        return selection_value(kind,code,locale)
    router.add_api_route(path,read,methods=['GET'],name=kind+'-read')
    router.add_api_route(path,create,methods=['POST'],status_code=201,name=kind+'-create')
    router.add_api_route(path+'/selection',selection,methods=['GET'],name=kind+'-selection')
    router.add_api_route(path+'/{code}',edit,methods=['PATCH'],name=kind+'-edit')

register('levels','/api/ppr/education-levels')
register('document-kinds','/api/ppr/document-kinds')
