from app.data_exchange.vacation_validation import validate_period


def codes(raw: str) -> set[str]: return {item.code for item in validate_period(raw)}


def test_invalid_and_reversed_dates_need_review() -> None:
    assert "PERIOD_DATE_INVALID" in codes("31.02.2026 по 02.03.2026")
    assert "PERIOD_END_BEFORE_START" in codes("10.03.2026 по 02.03.2026")


def test_incomplete_multiple_and_duration_conflict_are_not_auto_corrected() -> None:
    assert "PERIOD_INCOMPLETE" in codes("с 01.03.2026")
    assert "MULTIPLE_PERIODS_REVIEW_REQUIRED" in codes("01.03.2026-02.03.2026; 05.03.2026-06.03.2026")
    assert "PERIOD_DURATION_CONFLICT" in codes("01.03.2026 по 03.03.2026, 5 дней")
