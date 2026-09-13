from app.services.hr_import_qualification_category_service import parse_qualification_categories


def test_expiry_date_is_converted_to_exact_five_year_earlier_assignment_date():
    rows = parse_qualification_categories('Высшая до 15.06.2030 г. "терапия"')
    assert len(rows) == 1
    assert rows[0].category == "highest"
    assert rows[0].specialty == "терапия"
    assert rows[0].assigned_at == "2025-06-15"
    assert rows[0].assigned_at_calculated is True
    assert rows[0].review_status == "AUTO_READY"


def test_missing_specialty_is_reviewable_not_invented():
    row = parse_qualification_categories("Первая до 15.06.2030 г.")[0]
    assert row.review_status == "REVIEW_REQUIRED"
    assert row.review_reason in {"CATEGORY_MISSING_SPECIALTY", "CATEGORY_ASSIGNED_DATE_MISSING_OR_AMBIGUOUS"}


def test_year_only_date_is_not_promoted_to_a_date():
    row = parse_qualification_categories("Вторая хирургия 2030")[0]
    assert row.assigned_at == ""
    assert row.review_reason == "CATEGORY_ASSIGNED_DATE_MISSING_OR_AMBIGUOUS"


def test_june_control_list_category_with_quoted_specialty_is_parsed_without_prefix_garbage():
    row = parse_qualification_categories('1.Высшая до 11.07.2030 г. "Анестезиология и реаниматология"(перфузиология, токсикология)(взрослая)')[0]
    assert row.specialty == "Анестезиология и реаниматология"
    assert row.assigned_at == "2025-07-11"
    assert row.review_status == "AUTO_READY"


def test_unquoted_control_list_remainder_is_not_saved_as_specialty():
    row = parse_qualification_categories("1.Высшая до 18.07.2030г. Лучевая диагностика Рентгенология")[0]
    assert row.specialty == ""
    assert row.review_status == "REVIEW_REQUIRED"
    assert row.review_reason in {"CATEGORY_MISSING_SPECIALTY", "CATEGORY_ASSIGNED_DATE_MISSING_OR_AMBIGUOUS"}
