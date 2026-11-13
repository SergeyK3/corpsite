from datetime import date

from app.services.personnel_headcount_trend_service import _historical_counts


def test_verified_events_count_unique_employees_at_each_month_end():
    cards = {1: "active", 2: "active", 3: "inactive"}
    events = [
        {"employee_id": 1, "event_type": "HIRE", "effective_date": date(2025, 12, 1)},
        {"employee_id": 2, "event_type": "HIRE", "effective_date": date(2026, 2, 1)},
        {"employee_id": 3, "event_type": "HIRE", "effective_date": date(2026, 1, 15)},
        {"employee_id": 3, "event_type": "TERMINATION", "effective_date": date(2026, 3, 31)},
    ]

    assert _historical_counts(cards, events, today=date(2026, 4, 10), current_total=2) == {
        1: 2, 2: 3, 3: 3,
    }


def test_incomplete_history_cannot_supply_past_values():
    cards = {1: "active", 2: "active"}
    events = [{"employee_id": 1, "event_type": "HIRE", "effective_date": date(2025, 1, 1)}]

    assert _historical_counts(cards, events, today=date(2026, 4, 10), current_total=2) is None
