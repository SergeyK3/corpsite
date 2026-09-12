from app.services.hr_import_general_first_pass_service import _separate_source_parts, parse_full_name, surname_alphabet


def test_parse_full_name_accepts_surname_name_patronymic() -> None:
    parts, reason = parse_full_name("Тулеутаев Мухтар Есенжанович")

    assert reason is None
    assert parts is not None
    assert (parts.last_name, parts.first_name, parts.middle_name) == (
        "Тулеутаев",
        "Мухтар",
        "Есенжанович",
    )


def test_parse_full_name_accepts_two_components_without_patronymic() -> None:
    parts, reason = parse_full_name("Алиев Али")

    assert reason is None
    assert parts is not None
    assert (parts.last_name, parts.first_name, parts.middle_name) == ("Алиев", "Али", None)


def test_separate_source_fields_take_precedence_over_full_name_parsing() -> None:
    parts = _separate_source_parts(
        {"last_name": "Тулеутаев", "first_name": "Мухтар", "middle_name": "Есенжанович"}
    )

    assert parts is not None
    assert (parts.last_name, parts.first_name, parts.middle_name) == (
        "Тулеутаев",
        "Мухтар",
        "Есенжанович",
    )


def test_parse_full_name_leaves_ambiguous_four_components_for_review() -> None:
    parts, reason = parse_full_name("Де Ла Круз Мария")

    assert parts is None
    assert reason == "NAME_COMPONENT_COUNT_UNCERTAIN"


def test_surname_alphabet_uses_first_letter_without_transliteration() -> None:
    assert surname_alphabet("  Әлиев") == "Ә"
    assert surname_alphabet("-Қали") == "Қ"
