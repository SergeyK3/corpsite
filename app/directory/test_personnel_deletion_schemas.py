"""HTTP contracts for WP-TD-002 (approval foundation only)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TestPersonnelPreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: Literal["full_name"] = "full_name"
    mask: str | None = None
    person_ids: list[int] = Field(default_factory=list, max_length=200)
    application_ids: list[int] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def require_selector(self):
        if not self.mask and not self.person_ids and not self.application_ids:
            raise ValueError("mask or exact IDs are required")
        if any(value <= 0 for value in (*self.person_ids, *self.application_ids)):
            raise ValueError("technical IDs must be positive")
        return self


class TestPersonnelTargetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: int = Field(..., ge=1)
    application_id: int = Field(..., ge=1)


class TestPersonnelDraftCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    basis: Literal["PROVENANCE", "LEGACY_MANIFEST"]
    process_type: Literal["APPLICANT_ONLY"] = "APPLICANT_ONLY"
    reason_code: Literal[
        "LEGACY_SYNTHETIC_TEST_DATA",
        "PROVENANCE_TEST_RUN_CLEANUP",
        "DUPLICATE_SYNTHETIC_FIXTURE",
        "OTHER_APPROVED_TEST_DATA",
    ]
    search_field: Literal["full_name"] = "full_name"
    original_mask: str | None = None
    targets: list[TestPersonnelTargetIn] = Field(..., min_length=1, max_length=200)
    idempotency_key: str = Field(..., min_length=1, max_length=128)

    @field_validator("idempotency_key")
    @classmethod
    def nonblank_idempotency_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("idempotency_key must not be blank")
        return value


class TestPersonnelCommandIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(..., ge=1)
    idempotency_key: str = Field(..., min_length=1, max_length=128)
    comment: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("idempotency_key")
    @classmethod
    def nonblank_idempotency_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("idempotency_key must not be blank")
        return value

    @field_validator("comment")
    @classmethod
    def nonblank_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("comment must not be blank")
        return value


class TestPersonnelDecisionIn(TestPersonnelCommandIn):
    submitted_synthetic_confirmed: bool = False
