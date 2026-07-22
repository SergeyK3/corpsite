"""Tests for composite numbered education parsing in HR import."""
from __future__ import annotations

from app.services.hr_import_document_parser import (
    parse_education_graduation_fragment,
    parse_education_raw,
    split_education_institution_pieces,
    split_raw_fragments,
)
from app.services.hr_import_profile_service import build_import_profile


COMPOSITE_RAW = (
    "1. Семипалатинский бизнес-колледж, 2006г. "
    "2. Семипалатинская государственная медицинская академия"
)


def test_split_raw_fragments_inline_numbered_items() -> None:
    fragments = split_raw_fragments(COMPOSITE_RAW)
    assert len(fragments) == 2
    assert fragments[0].startswith("1.")
    assert fragments[1].startswith("2.")


def test_parse_education_raw_creates_separate_records() -> None:
    parsed = parse_education_raw(COMPOSITE_RAW)
    assert len(parsed) == 2

    first, second = parsed
    assert first.fragment_index == 0
    assert second.fragment_index == 1
    assert "бизнес-колледж" in (first.organization or "").lower()
    assert first.parsed_issued_at is not None
    assert first.parsed_issued_at.year == 2006
    assert "академ" in (second.organization or "").lower()
    assert second.parsed_issued_at is None


def test_build_import_profile_has_independent_education_records() -> None:
    profile = build_import_profile({"education_raw": COMPOSITE_RAW})
    records = profile["education_records"]
    assert len(records) == 2
    assert records[0]["source_text"] != records[1]["source_text"]
    assert records[0]["completed_at"] == "2006"
    assert not records[1]["completed_at"]
    assert "бизнес-колледж" in records[0]["institution"].lower()
    assert "академ" in records[1]["institution"].lower()


def test_admission_and_graduation_years_extracted() -> None:
    parsed = parse_education_graduation_fragment(
        "1. КазНМУ, поступил 2001, окончил 2006",
        fragment_index=0,
    )
    assert parsed.parsed_start_at is not None
    assert parsed.parsed_start_at.year == 2001
    assert parsed.parsed_end_at is not None
    assert parsed.parsed_end_at.year == 2006


SHARED_CONTEXT_RAW = (
    "1. Семипалатинский бизнес-колледж, 2006г. "
    "2. Семипалатинская государственная медицинская академия, 2012г. "
    "Специальность «Лечебное дело», квалификация «врач»"
)


def test_shared_context_tail_is_separated_from_institutions() -> None:
    institutions, shared_tail = split_education_institution_pieces(SHARED_CONTEXT_RAW)
    assert len(institutions) == 2
    assert "Специальность" in shared_tail
    assert "квалификация" in shared_tail


def test_shared_specialty_and_qualification_copied_to_all_records() -> None:
    parsed = parse_education_raw(SHARED_CONTEXT_RAW)
    assert len(parsed) == 2
    assert all(item.specialty == "Лечебное дело" for item in parsed)
    assert all(item.qualification == "врач" for item in parsed)
    assert all(item.shared_context_ambiguous for item in parsed)
    assert all("shared_context_ambiguous" in item.parse_method for item in parsed)


def test_build_import_profile_propagates_shared_context_fields() -> None:
    profile = build_import_profile({"education_raw": SHARED_CONTEXT_RAW})
    records = profile["education_records"]
    assert len(records) == 2
    assert records[0]["specialty"] == "Лечебное дело"
    assert records[1]["specialty"] == "Лечебное дело"
    assert records[0]["qualification"] == "врач"
    assert records[1]["qualification"] == "врач"


def test_diploma_specialty_column_applies_to_all_numbered_institutions() -> None:
    parsed = parse_education_raw(COMPOSITE_RAW, "Лечебное дело")
    assert len(parsed) == 2
    assert parsed[0].specialty == "Лечебное дело"
    assert parsed[1].specialty == "Лечебное дело"
    assert parsed[0].shared_context_ambiguous
    assert parsed[1].shared_context_ambiguous
