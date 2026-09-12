from datetime import date

from app.services.hr_import_additional_status_service import (
    FACT_DISABILITY,
    FACT_PENSION,
    REVIEW_READY,
    REVIEW_REQUIRED,
    parse_control_list_note,
)


def test_complete_disability_note_is_structured_without_retaining_source_text() -> None:
    result = parse_control_list_note("Инвалидность II группы, M54.5, с 01.02.2024")
    assert result.requires_manual_review is False
    assert len(result.facts) == 1
    fact = result.facts[0]
    assert fact.fact_kind == FACT_DISABILITY
    assert fact.effective_date == date(2024, 2, 1)
    assert fact.disability_group == "II"
    assert fact.icd10_code == "M54.5"
    assert fact.review_status == REVIEW_READY


def test_incomplete_disability_and_pension_require_review_without_inventing_fields() -> None:
    disability = parse_control_list_note("инвалид III группы")
    assert disability.facts[0].fact_kind == FACT_DISABILITY
    assert disability.facts[0].effective_date is None
    assert disability.facts[0].icd10_code is None
    assert disability.facts[0].review_status == REVIEW_REQUIRED

    pension = parse_control_list_note("пенсионер")
    assert pension.facts[0].fact_kind == FACT_PENSION
    assert pension.facts[0].effective_date is None
    assert pension.facts[0].review_status == REVIEW_REQUIRED


def test_maternity_note_is_ignored_and_other_note_is_review_only() -> None:
    assert parse_control_list_note("декретный отпуск").facts == ()
    assert parse_control_list_note("декретный отпуск").requires_manual_review is False
    assert parse_control_list_note("сведения уточняются").facts == ()
    assert parse_control_list_note("сведения уточняются").requires_manual_review is True
