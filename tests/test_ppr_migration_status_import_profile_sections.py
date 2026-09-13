from app.services.ppr_migration_status_projection_service import _first_import_profile_problem


def test_import_profile_award_without_date_requires_specific_correction() -> None:
    assert _first_import_profile_problem(
        "awards", [{"title": "Почётная награда", "date": ""}], {"award_records": []}
    ) == "AWARDS_IMPORT_MISSING_DATE"


def test_import_profile_academic_degree_without_date_requires_specific_correction() -> None:
    assert _first_import_profile_problem(
        "academic_degrees_titles",
        [{"label": "Кандидат медицинских наук", "completed_at": ""}],
        {"degrees": {"records": []}},
    ) == "ACADEMIC_DEGREES_TITLES_IMPORT_MISSING_COMPLETED_AT"
