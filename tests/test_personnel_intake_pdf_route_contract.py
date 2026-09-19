"""Route contract used by the protected Next.js personnel-PDF handler.

This test has no database dependency: it prevents the UI URL from drifting away
from the FastAPI endpoint that supplies the current intake payload.
"""

from app.directory.router import router
from app.directory.personnel_intake_schemas import EmploymentTenureCalculateIn


def test_hr_intake_draft_route_is_registered_for_pdf_pipeline() -> None:
    routes = {
        (route.path, frozenset(route.methods or set()))
        for route in router.routes
        if hasattr(route, "methods")
    }

    assert (
        "/directory/personnel-applications/{application_id}/intake/draft",
        frozenset({"GET"}),
    ) in routes


def test_tenure_input_accepts_unverified_canonical_normalizations() -> None:
    """A v2 PDF must be able to calculate tenure before HR normalization exists."""
    parsed = EmploymentTenureCalculateIn.model_validate(
        {
            "calculation_date": "2026-09-19",
            "records": [
                {
                    "record_id": "d83f745d-37f8-4331-82bd-9c6a2af1631a",
                    "organization_original": "Поликлиника 3",
                    "organization_normalized": None,
                    "position_original": "врач хирург",
                    "position_normalized": None,
                    "start_date": "2020-08-01",
                    "end_date": None,
                }
            ],
        }
    )

    assert parsed.records[0].organization_normalized is None
    assert parsed.records[0].position_normalized is None
