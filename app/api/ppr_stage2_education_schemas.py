from pydantic import BaseModel, Field

class Stage2PreviewRequest(BaseModel):
    stage0_cohort_run_id: int = Field(ge=1)
class Stage2RunRequest(BaseModel):
    stage_run_id: int = Field(ge=1)
class Stage2SkipRequest(BaseModel):
    reason: str = Field(min_length=1,max_length=1000)
class Stage2CancelRequest(BaseModel):
    reason: str = Field(min_length=1,max_length=1000)
class Stage2AcceptRequest(BaseModel):
    stage_run_id: int = Field(ge=1)
    acceptance_fingerprint: str | None = Field(default=None,min_length=64,max_length=64)
