"""Stateless API for employment tenure calculation (intake / on-behalf)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from app.directory.common import as_http500
from app.directory.personnel_intake_schemas import (
    EmploymentTenureCalculateIn,
    EmploymentTenureCalculateOut,
    employment_tenure_to_out,
)
from app.personnel_intake.domain.employment_tenure import calculate_employment_tenure

router = APIRouter(prefix="/intake/employment-tenure", tags=["personnel-intake-tenure"])


@router.post("/calculate", response_model=EmploymentTenureCalculateOut)
def post_employment_tenure_calculate(body: EmploymentTenureCalculateIn) -> EmploymentTenureCalculateOut:
    """Calculate merged employment tenure for intake employment biography rows."""
    try:
        result = calculate_employment_tenure(body.records)
        return employment_tenure_to_out(result)
    except Exception as exc:
        raise as_http500(exc)
