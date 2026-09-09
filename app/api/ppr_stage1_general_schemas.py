from typing import Any
from pydantic import BaseModel, Field
class Stage1PreviewRequest(BaseModel): stage0_cohort_run_id:int=Field(ge=1)
class Stage1RunRequest(BaseModel): stage1_run_id:int=Field(ge=1)
class Stage1ParticipantOut(BaseModel):
    position:int; employee_id:int; person_id:int; source_row_id:int; source_row_number:int|None=None; display_name:str|None=None
    source:dict[str,Any]; current:dict[str,Any]; proposal:dict[str,Any]; conflicts:list[dict[str,Any]]; status:str; error_code:str|None=None; error_detail:str|None=None
class Stage1RunOut(BaseModel): run:dict[str,Any]; participants:list[Stage1ParticipantOut]; counts:dict[str,int]; organization_timezone:str
