from datetime import date
from decimal import Decimal

import pytest

from app.personnel_intake.domain.training_summary import (
    TrainingSummaryRecord,
    add_calendar_months,
    add_calendar_years,
    calculate_expiring_certificates,
    calculate_training_hours_last_5y,
    training_window_start,
)


AS_OF = date(2026, 6, 16)


def _record(
    *,
    title: str = "Course",
    completed_at: date | None = date(2024, 1, 10),
    hours: str | Decimal | None = "16",
    document_type: str = "certificate",
    lifecycle_status: str = "ACTIVE",
) -> TrainingSummaryRecord:
    parsed_hours = None if hours is None else Decimal(str(hours))
    return TrainingSummaryRecord(
        title=title,
        completed_at=completed_at,
        hours=parsed_hours,
        document_type=document_type,
        lifecycle_status=lifecycle_status,
    )


def test_training_window_start_handles_leap_day():
    assert training_window_start(date(2024, 2, 29)) == date(2019, 2, 28)


def test_hours_sum_includes_boundary_and_excludes_outside_window():
    records = [
        _record(title="Inside", completed_at=date(2021, 6, 16), hours="40"),
        _record(title="Too old", completed_at=date(2021, 6, 15), hours="99"),
        _record(title="Future", completed_at=date(2026, 7, 1), hours="10"),
        _record(title="No hours", completed_at=date(2025, 1, 1), hours=None),
        _record(title="Voided", completed_at=date(2025, 2, 1), hours="8", lifecycle_status="VOIDED"),
    ]

    summary = calculate_training_hours_last_5y(records, as_of=AS_OF)

    assert summary["window_start"] == "2021-06-16"
    assert summary["training_hours_last_5y"] == 40
    assert summary["qualifying_records_count"] == 1


def test_hours_sum_from_mapping_with_legacy_year_to_field():
    summary = calculate_training_hours_last_5y(
        [
            {
                "course_name": "Legacy",
                "year_to": "2023-05-01",
                "hours": "12",
                "document_type": "certificate",
            }
        ],
        as_of=AS_OF,
    )
    assert summary["training_hours_last_5y"] == 12


def test_expiring_certificates_within_six_month_window():
    completed_at = add_calendar_years(AS_OF, -5)
    completed_at = add_calendar_months(completed_at, 3)
    records = [
        _record(title="Soon", completed_at=completed_at, document_type="certificate"),
        _record(title="Witness", completed_at=completed_at, document_type="witness"),
        _record(title="", completed_at=completed_at, document_type="certificate"),
    ]

    expiring = calculate_expiring_certificates(records, as_of=AS_OF)

    assert len(expiring) == 1
    assert expiring[0].title == "Soon"
    assert expiring[0].expires_at == add_calendar_years(completed_at, 5)
    assert expiring[0].days_remaining > 0


def test_expiring_certificates_exclude_expired_and_distant():
    expired_completed = add_calendar_years(AS_OF, -6)
    distant_completed = add_calendar_years(add_calendar_months(AS_OF, -7), -5)
    records = [
        _record(title="Expired", completed_at=expired_completed, document_type="certificate"),
        _record(title="Later", completed_at=distant_completed, document_type="certificate"),
        _record(title="Missing date", completed_at=None, document_type="certificate"),
    ]

    expiring = calculate_expiring_certificates(records, as_of=AS_OF)

    assert expiring == []


def test_empty_records_return_zero_hours_and_no_certificates():
    assert calculate_training_hours_last_5y([], as_of=AS_OF)["training_hours_last_5y"] == 0
    assert calculate_expiring_certificates([], as_of=AS_OF) == []
