from datetime import date

from app.services.ppr_migration_status_projection_service import (
    IMPORT_NOTE_PENSION_REVIEW_REASON,
    PENSION_AGE_REVIEW_REASON,
    _canonical_cell,
    _requires_pension_age_confirmation,
)


def test_pension_age_policy_uses_canonical_identity_at_report_date():
    assert _requires_pension_age_confirmation(
        general_record={"birth_date": date(1963, 9, 12), "iin": "630912300000"},
        import_card=None,
        report_date=date(2026, 9, 13),
    )
    assert not _requires_pension_age_confirmation(
        general_record={"birth_date": date(1963, 9, 14), "iin": "630914300000"},
        import_card=None,
        report_date=date(2026, 9, 13),
    )


def test_pension_age_policy_can_use_existing_selected_import_profile_without_writing_it():
    assert _requires_pension_age_confirmation(
        general_record={"birth_date": None, "iin": ""},
        import_card={"profile": {"basic": {"birth_date": "1960-06-24", "sex": "female", "iin": "600624450050"}}},
        report_date=date(2026, 9, 13),
    )


def test_additional_absence_is_review_required_when_selected_profile_reaches_pension_age():
    cell = _canonical_cell(
        {"person_id": 7, "person_updated_at": "v1", "stage0_cohort_run_id": 3, "stage0_participant_id": 7,
         "employee_id": 12, "org_unit_id": 1, "employee_person_id": 7, "is_active": True,
         "operational_status": "active", "person_status": "active", "merged_into_person_id": None},
        "additional", [], general_record={"birth_date": None, "iin": ""},
        import_card={"profile": {"basic": {"birth_date": "1960-06-24", "sex": "F", "iin": "600624450050"}}},
        report_date=date(2026, 9, 13),
    )
    assert (cell["status_code"], cell["reason_code"]) == ("REVIEW_REQUIRED", PENSION_AGE_REVIEW_REASON)


def test_explicit_pension_note_requires_review_even_before_pension_age():
    cell = _canonical_cell(
        {"person_id": 7, "person_updated_at": "v1", "stage0_cohort_run_id": 3, "stage0_participant_id": 7,
         "employee_id": 12, "org_unit_id": 1, "employee_person_id": 7, "is_active": True,
         "operational_status": "active", "person_status": "active", "merged_into_person_id": None},
        "additional", [], general_record={"birth_date": date(1990, 1, 1), "iin": "900101300000"},
        import_card={"batch_id": 809, "row_id": 19195, "note_raw": "пенсионер", "override_origin": "none", "profile": {"basic": {}}},
        report_date=date(2026, 9, 13),
    )
    assert (cell["status_code"], cell["reason_code"]) == ("REVIEW_REQUIRED", IMPORT_NOTE_PENSION_REVIEW_REASON)
    assert (cell["source_batch_id"], cell["source_row_id"]) == (809, 19195)
