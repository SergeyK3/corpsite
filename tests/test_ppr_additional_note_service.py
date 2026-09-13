from datetime import date

import pytest

from app.services.ppr_additional_note_service import _normalize_row, _safe_fingerprint


def test_pension_details_are_ready_only_when_kind_and_date_are_present():
    ready = _normalize_row("PENSION", {"pension_kind": "AGE", "effective_date": "2020-01-31"})
    assert ready == {
        "effective_date": date(2020, 1, 31),
        "disability_group": None,
        "icd10_code": None,
        "pension_kind": "AGE",
        "review_status": "AUTO_READY",
        "review_reason": None,
    }
    assert _normalize_row("PENSION", {"pension_kind": "SERVICE"})["review_status"] == "REVIEW_REQUIRED"


def test_disability_requires_structured_details_and_validates_icd10():
    ready = _normalize_row("DISABILITY", {"disability_group": "II", "effective_date": "2020-01-31", "icd10_code": "G35"})
    assert ready["review_status"] == "AUTO_READY"
    assert _normalize_row("DISABILITY", {"disability_group": "II"})["review_status"] == "REVIEW_REQUIRED"
    with pytest.raises(ValueError, match="ICD-10"):
        _normalize_row("DISABILITY", {"icd10_code": "not-a-code"})


def test_correction_fingerprint_does_not_contain_medical_values():
    fingerprint = _safe_fingerprint(person_id=7, fact_kind="DISABILITY", source_row_id=11, version=2, parent_id=9)
    assert len(fingerprint) == 64
    assert "G35" not in fingerprint
