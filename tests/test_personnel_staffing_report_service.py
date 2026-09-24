from datetime import date

from app.services.personnel_staffing_report_service import TURNOVER_CODES, _classify, calculate_staffing_metrics


def test_daily_average_includes_both_boundaries_and_does_not_double_count_additional_assignments():
    current, average, by_unit, incomplete = calculate_staffing_metrics([
        {"person_id": 1, "org_unit_id": 10, "start_date": date(2026, 1, 1), "end_date": date(2026, 1, 3)},
        {"person_id": 1, "org_unit_id": 10, "start_date": date(2026, 1, 1), "end_date": date(2026, 1, 3)},
        {"person_id": 2, "org_unit_id": 10, "start_date": date(2026, 1, 3), "end_date": None},
    ], date_from=date(2026, 1, 1), date_to=date(2026, 1, 3))
    assert (current, average, incomplete) == (2, 4 / 3, False)
    assert by_unit[10]["average_headcount"] == 4 / 3


def test_transfer_is_attributed_to_the_unit_for_each_calendar_day():
    _, _, by_unit, _ = calculate_staffing_metrics([
        {"person_id": 1, "org_unit_id": 10, "start_date": date(2026, 1, 1), "end_date": date(2026, 1, 2)},
        {"person_id": 1, "org_unit_id": 11, "start_date": date(2026, 1, 3), "end_date": None},
    ], date_from=date(2026, 1, 1), date_to=date(2026, 1, 3))
    assert by_unit[10]["average_headcount"] == 2 / 3
    assert by_unit[11]["average_headcount"] == 1 / 3


def test_turnover_only_uses_explicit_structured_reason_codes():
    assert [_classify(code) for code in TURNOVER_CODES] == list(TURNOVER_CODES.values())
    assert _classify("TRANSFER_TO_OTHER_EMPLOYER") is None
    assert _classify("вольное увольнение") is None
