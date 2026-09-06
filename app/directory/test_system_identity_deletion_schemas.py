"""HTTP input contracts for the read-only WP-TD-006B workflow."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TestSystemIdentitySearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_type: Literal["USER", "ROLE"]
    field: Literal["full_name", "login", "name", "code"]
    mask: str | None = None
    object_ids: list[int] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def require_selector(self):
        if not self.mask and not self.object_ids:
            raise ValueError("mask or exact technical IDs are required")
        if any(value <= 0 for value in self.object_ids):
            raise ValueError("technical IDs must be positive")
        return self


class TestSystemIdentityTargetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_type: Literal["USER", "ROLE"]
    object_id: int = Field(..., ge=1)


class TestSystemIdentityPreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[TestSystemIdentityTargetIn] = Field(..., min_length=1, max_length=200)
