# tests/test_wp_cl_007_contacts_normalization.py
"""Unit tests for WP-CL-007 contacts normalization layer."""
from __future__ import annotations

import inspect
from datetime import datetime

import pytest

from app.control_list_import.contact_normalization.email import normalize_contact_email
from app.control_list_import.contact_normalization.service import ContactNormalizationService
from app.control_list_import.domain.contact_candidate import ContactReadinessStatus
from app.control_list_import.domain.models import (
    MappingProfileColumnSnapshot,
    MappingProfileSheetSnapshot,
    MappingProfileSnapshot,
)
from app.control_list_import.domain.person_match_models import MatchReason, MatchStatus, PersonMatchResult
from app.control_list_import.domain.staging_models import StagingCellInput, StagingRowInput
from app.control_list_import.domain.vocabulary import (
    PARSER_CODE_CONTACT_ADDRESS,
    PARSER_CODE_CONTACT_EMAIL,
    PARSER_CODE_CONTACT_PHONE,
    SEMANTIC_FIELD_CONTACT_EMAIL,
    SEMANTIC_FIELD_CONTACT_PHONE,
    SEMANTIC_FIELD_CONTACT_REGISTRATION_ADDRESS,
    SEMANTIC_FIELD_CONTACT_RESIDENCE_ADDRESS,
)
from app.control_list_import.normalization.phone import normalize_phone
from app.db.models.control_list_mapping import (
    EMPLOYMENT_MODE_PRIMARY,
    PERSONNEL_CATEGORY_DOCTOR,
    PROFILE_STATUS_ACTIVE,
    SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
)


def _contact_columns() -> list[MappingProfileColumnSnapshot]:
    return [
        MappingProfileColumnSnapshot(
            profile_column_id=1,
            profile_sheet_id=1,
            column_index=5,
            column_letter="E",
            raw_header="Телефон",
            semantic_field=SEMANTIC_FIELD_CONTACT_PHONE,
            parser_code=PARSER_CODE_CONTACT_PHONE,
            is_required=False,
        ),
        MappingProfileColumnSnapshot(
            profile_column_id=2,
            profile_sheet_id=1,
            column_index=6,
            column_letter="F",
            raw_header="Email",
            semantic_field=SEMANTIC_FIELD_CONTACT_EMAIL,
            parser_code=PARSER_CODE_CONTACT_EMAIL,
            is_required=False,
        ),
        MappingProfileColumnSnapshot(
            profile_column_id=3,
            profile_sheet_id=1,
            column_index=7,
            column_letter="G",
            raw_header="Адрес проживания",
            semantic_field=SEMANTIC_FIELD_CONTACT_RESIDENCE_ADDRESS,
            parser_code=PARSER_CODE_CONTACT_ADDRESS,
            is_required=False,
        ),
        MappingProfileColumnSnapshot(
            profile_column_id=4,
            profile_sheet_id=1,
            column_index=8,
            column_letter="H",
            raw_header="Адрес регистрации",
            semantic_field=SEMANTIC_FIELD_CONTACT_REGISTRATION_ADDRESS,
            parser_code=PARSER_CODE_CONTACT_ADDRESS,
            is_required=False,
        ),
    ]


def _profile() -> MappingProfileSnapshot:
    sheet = MappingProfileSheetSnapshot(
        profile_sheet_id=1,
        profile_id=10,
        sheet_name="врачи",
        personnel_category=PERSONNEL_CATEGORY_DOCTOR,
        employment_mode=EMPLOYMENT_MODE_PRIMARY,
        sheet_purpose=SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
        header_row_override=3,
        columns=_contact_columns(),
    )
    return MappingProfileSnapshot(
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        profile_name="Default",
        description=None,
        status=PROFILE_STATUS_ACTIVE,
        created_at=datetime(2026, 7, 17, 12, 0, 0),
        created_by=1,
        updated_at=None,
        sheets=[sheet],
    )


def _row(
    *,
    phone: str | None = "+7 (701) 123-45-67",
    email: str | None = "user@example.com",
    residence: str | None = "г. Алматы, ул. Абая 10",
    registration: str | None = "г. Алматы, ул. Абая 10",
    row_id: int = 100,
) -> StagingRowInput:
    cells: list[StagingCellInput] = []
    if phone is not None:
        cells.append(StagingCellInput(column_index=5, raw_value=phone))
    if email is not None:
        cells.append(StagingCellInput(column_index=6, raw_value=email))
    if residence is not None:
        cells.append(StagingCellInput(column_index=7, raw_value=residence))
    if registration is not None:
        cells.append(StagingCellInput(column_index=8, raw_value=registration))
    return StagingRowInput(
        row_id=row_id,
        sheet_name="врачи",
        excel_row_number=5,
        row_kind="data",
        cells=tuple(cells),
    )


def _match_result(
    *,
    status: MatchStatus = MatchStatus.EXACT,
    recommended_person_id: int | None = 42,
    source_row_id: int = 100,
) -> PersonMatchResult:
    return PersonMatchResult(
        import_run_id=7,
        source_row_id=source_row_id,
        status=status,
        match_candidates=(),
        primary_reason=MatchReason.EXACT_IIN,
        reasons=(MatchReason.EXACT_IIN,),
        confidence=1.0,
        recommended_person_id=recommended_person_id,
    )


def test_normalize_phone_reuses_wp_cl_004():
    result = normalize_phone("+7 (701) 123-45-67")
    assert result.digits == "77011234567"
    assert result.is_valid


def test_normalize_contact_email_valid():
    result = normalize_contact_email("  User@Example.COM  ")
    assert result.address == "user@example.com"
    assert result.is_valid


def test_normalize_contact_email_invalid():
    result = normalize_contact_email("not-an-email")
    assert not result.is_valid
    assert "contact_email_unrecognized_format" in result.issues


def test_matched_person_reaches_normalization_ready():
    candidate = ContactNormalizationService().normalize_row(
        row=_row(),
        profile=_profile(),
        person_match=_match_result(recommended_person_id=42),
        import_run_id=7,
    )
    assert candidate is not None
    assert candidate.matched_person_id == 42
    assert candidate.readiness_status == ContactReadinessStatus.NORMALIZATION_READY
    assert candidate.is_normalization_ready


def test_normalization_ready_does_not_authorize_ppr_contact_apply():
    candidate = ContactNormalizationService().normalize_row(
        row=_row(),
        profile=_profile(),
        person_match=_match_result(recommended_person_id=42),
        import_run_id=7,
    )
    assert candidate is not None
    assert candidate.is_normalization_ready
    assert type(candidate).__name__ == "ContactCandidate"
    assert not hasattr(candidate, "employee_id")
    assert not hasattr(candidate, "contact_id")
    assert not hasattr(candidate, "authorizes_apply")
    service_source = inspect.getsource(ContactNormalizationService).lower()
    assert "insert into" not in service_source
    assert "update " not in service_source
    assert "merge" not in service_source


def test_unmatched_person_still_creates_candidate():
    candidate = ContactNormalizationService().normalize_row(
        row=_row(),
        profile=_profile(),
        person_match=_match_result(status=MatchStatus.NOT_FOUND, recommended_person_id=None),
        import_run_id=7,
    )
    assert candidate is not None
    assert candidate.matched_person_id is None
    assert candidate.readiness_status == ContactReadinessStatus.PERSON_UNMATCHED


def test_ambiguous_match_requires_review():
    candidate = ContactNormalizationService().normalize_row(
        row=_row(),
        profile=_profile(),
        person_match=_match_result(status=MatchStatus.AMBIGUOUS, recommended_person_id=None),
        import_run_id=7,
    )
    assert candidate is not None
    assert candidate.readiness_status == ContactReadinessStatus.REVIEW_REQUIRED


def test_invalid_person_match_status():
    candidate = ContactNormalizationService().normalize_row(
        row=_row(),
        profile=_profile(),
        person_match=_match_result(status=MatchStatus.INVALID, recommended_person_id=None),
        import_run_id=7,
    )
    assert candidate is not None
    assert candidate.readiness_status == ContactReadinessStatus.PERSON_MATCH_INVALID


def test_invalid_phone_and_email_add_issues():
    candidate = ContactNormalizationService().normalize_row(
        row=_row(phone="123", email="bad-email"),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidate is not None
    assert "phone_invalid_length" in candidate.field_issues[SEMANTIC_FIELD_CONTACT_PHONE]
    assert "contact_email_unrecognized_format" in candidate.field_issues[SEMANTIC_FIELD_CONTACT_EMAIL]
    assert candidate.readiness_status == ContactReadinessStatus.REVIEW_REQUIRED


def test_residence_and_registration_addresses():
    candidate = ContactNormalizationService().normalize_row(
        row=_row(
            residence="  г. Алматы,   пр. Абая 10  ",
            registration="г. Астана, ул. Кенесары 1",
        ),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidate is not None
    assert candidate.residence_address.text == "г. Алматы, пр. Абая 10"
    assert candidate.registration_address.text == "г. Астана, ул. Кенесары 1"


def test_completely_empty_contacts_skip_candidate():
    candidate = ContactNormalizationService().normalize_row(
        row=_row(phone=None, email=None, residence=None, registration=None),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidate is None


def test_technical_empty_addresses_skip_when_no_other_contacts():
    candidate = ContactNormalizationService().normalize_row(
        row=_row(phone=None, email=None, residence="-", registration="н/д"),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidate is None


def test_provenance_fields():
    candidate = ContactNormalizationService().normalize_row(
        row=_row(row_id=555),
        profile=_profile(),
        person_match=_match_result(source_row_id=555),
        import_run_id=99,
    )
    assert candidate is not None
    assert candidate.import_run_id == 99
    assert candidate.source_row_id == 555
    assert candidate.source_sheet_name == "врачи"
    assert candidate.source_excel_row_number == 5
    assert candidate.profile_code == "control_list_default"


def test_service_has_no_db_or_ppr_writes():
    source = inspect.getsource(ContactNormalizationService).lower()
    assert "sqlalchemy" not in source
    assert "insert into" not in source
    assert "update " not in source
    assert "delete from" not in source
    assert "employee_id" not in source
    assert "persons" not in source
