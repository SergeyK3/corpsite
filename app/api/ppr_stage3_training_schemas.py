from pydantic import BaseModel, Field

class Stage3PreviewRequest(BaseModel):
    stage0_cohort_run_id: int = Field(ge=1)
class Stage3CreateRunRequest(Stage3PreviewRequest):
    preview_fingerprint: str = Field(min_length=64,max_length=64)
class Stage3SkipRequest(BaseModel):
    reason: str = Field(min_length=1,max_length=1000)
class Stage3CancelRequest(BaseModel):
    reason: str = Field(min_length=1,max_length=1000)
class Stage3AcceptRequest(BaseModel):
    stage_run_id: int = Field(ge=1)
    acceptance_fingerprint: str | None = Field(default=None,min_length=64,max_length=64)
