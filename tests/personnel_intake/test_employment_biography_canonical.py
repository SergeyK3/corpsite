from datetime import date

from app.personnel_intake.domain.employment_biography import normalize_employment_biography_payload
from app.personnel_intake.domain.employment_tenure import calculate_employment_tenure
from app.personnel_intake.domain.payload_canonical import additional_none_conflicts, normalize_intake_payload


def test_legacy_employment_row_is_saved_in_canonical_shape_without_touching_education() -> None:
    payload = {
        "education": [{"institution": "Медицинский университет"}],
        "employment_biography": [{
            "year_from": "2020-08-01",
            "year_to": "",
            "organization": "Поликлиника 3 г. Астаны",
            "position": "врач хирург амбулаторного приема",
            "reason_for_leaving": "",
        }],
    }

    normalized = normalize_employment_biography_payload(payload)

    assert normalized["education"] == payload["education"]
    assert normalized["employment_biography"] == [{
        "record_id": normalized["employment_biography"][0]["record_id"],
        "start_date": "2020-08-01", "end_date": None,
        "organization_original": "Поликлиника 3 г. Астаны",
        "organization_normalized": None,
        "city": None,
        "position_original": "врач хирург амбулаторного приема",
        "position_normalized": None,
        "reason_for_leaving": None, "note": None,
        "verification_status": "requires_review", "evidence_document_ids": [],
    }]


def test_tenure_uses_canonical_dates_and_open_period() -> None:
    result = calculate_employment_tenure([{
        "record_id": "record", "start_date": "2020-08-01", "end_date": None,
        "organization_original": "Поликлиника", "position_original": "врач",
    }], calculation_date=date(2020, 8, 11))

    assert result.records[0].is_open_ended is True
    assert result.records[0].days == 10


def test_v2_payload_normalizes_legacy_rows_and_rejects_public_review_fields() -> None:
    result = normalize_intake_payload({
        "contacts": {"email": "", "mobile_phone": "8 (777) 237-88-55"},
        "personal": {"personnel_number": "FORBIDDEN", "photo_file_id": ""},
        "education": [{"institution": "ВУЗ", "year_from": "2013-09-01", "year_to": "2020-06-30", "diploma_number": "D"}],
        "training": [{"course_name": "Онкология", "hours": "840"}],
        "relatives": [{"relationship": "крёстная мать", "birth_year": "1996-11-21", "work_place": ""}],
        "additional": {"awards_none": True, "awards": [{"name": "Награда"}]},
        "employment_biography": [{"organization": "Клиника", "position": "врач-хирург", "verification_status": "verified", "organization_normalized": "Подмена"}],
    })
    assert result["schema_version"] == 2
    assert "personnel_number" not in result["personal"]
    assert result["contacts"] == {"email": None, "mobile_phone": "+77772378855", "residence_address": None, "registration_address": None}
    assert result["education"][0]["institution_original"] == "ВУЗ"
    assert result["education"][0]["document_number"] == "D"
    assert result["training"][0]["hours"] == 840
    assert result["relatives"][0]["relationship"] == "другое"
    assert result["relatives"][0]["relationship_other"] == "крёстная мать"
    assert len(result["additional"]["awards"]) == 1
    assert result["additional"]["awards"][0]["record_id"]
    assert result["additional"]["awards_none"] is False
    assert "verification_status" not in result["employment_biography"][0]


def test_none_flag_never_drops_legacy_records_and_is_rejected_on_new_save() -> None:
    raw = {"additional": {"awards_none": True, "awards": [{"name": "Награда"}]}}
    normalized = normalize_intake_payload(raw)
    assert normalized["additional"]["awards"][0]["name"] == "Награда"
    assert normalized["additional"]["awards_none"] is False
    assert additional_none_conflicts(raw) == ["awards"]
