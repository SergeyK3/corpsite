from app.ppr_migration.education_kind_policy import REVIEW_REQUIRED, classify_education_kind


def test_allowlist_does_not_default_unknown_text_to_basic():
    assert classify_education_kind("unknown educational category").outcome == REVIEW_REQUIRED


def test_allowlist_specific_markers_and_basic_are_deterministic():
    assert classify_education_kind("врач-интерн").kind == "internship"
    assert classify_education_kind("ординатура").kind == "residency"
    assert classify_education_kind("магистр").kind == "masters"
    assert classify_education_kind("доктор философии").kind == "phd"
    assert classify_education_kind("Высшее образование, диплом").kind == "basic"


def test_allowlist_fails_closed_for_ambiguous_and_postgraduate():
    assert classify_education_kind("магистратура и резидентура").outcome == REVIEW_REQUIRED
    assert classify_education_kind("послевузовское образование").outcome == REVIEW_REQUIRED
