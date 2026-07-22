"""Integration tests: education parser output → date quality remarks."""
from __future__ import annotations

from app.services.hr_import_document_parser import (
    EDUCATION_SHARED_CONTEXT_REMARK,
    parse_education_graduation_fragment,
    parse_education_raw,
)
from app.services.hr_import_training_date_quality_service import (
    TRAINING_DATE_QUALITY_REMARK,
    assess_normalized_record_date_quality,
)


SHARED_CONTEXT_RAW = (
    "1. Семипалатинский бизнес-колледж, 2006г. "
    "2. Семипалатинская государственная медицинская академия, 2012г. "
    "Специальность «Лечебное дело», квалификация «врач»"
)


def test_year_only_graduation_triggers_quality_remark() -> None:
    parsed = parse_education_graduation_fragment(
        "1. Семипалатинский бизнес-колледж, 2006г.",
        fragment_index=0,
    )
    remarks = assess_normalized_record_date_quality(
        {
            "record_kind": "education",
            "title": parsed.organization,
            "issue_date": parsed.parsed_issued_at.isoformat() if parsed.parsed_issued_at else None,
            "source_text": parsed.raw_text,
        }
    )
    assert remarks == [TRAINING_DATE_QUALITY_REMARK]


def test_missing_dates_trigger_quality_remark() -> None:
    parsed = parse_education_graduation_fragment(
        "2. Семипалатинская государственная медицинская академия",
        fragment_index=1,
    )
    remarks = assess_normalized_record_date_quality(
        {
            "record_kind": "education",
            "title": parsed.organization,
            "source_text": parsed.raw_text,
        }
    )
    assert remarks == [TRAINING_DATE_QUALITY_REMARK]


def test_shared_context_ambiguity_quality_remark() -> None:
    parsed = parse_education_raw(SHARED_CONTEXT_RAW)
    for item in parsed:
        remarks = assess_normalized_record_date_quality(
            {
                "record_kind": "education",
                "title": item.organization,
                "parse_method": item.parse_method,
                "source_text": item.raw_text,
            }
        )
        assert EDUCATION_SHARED_CONTEXT_REMARK in remarks
