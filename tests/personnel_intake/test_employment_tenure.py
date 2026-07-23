"""Tests for employment tenure calculation."""
from __future__ import annotations

from datetime import date

from app.personnel_intake.domain.employment_tenure import (
    END_BEFORE_START_WARNING,
    MISSING_START_WARNING,
    calculate_employment_tenure,
    merge_employment_intervals,
)


def _record(
    *,
    organization: str = "Org",
    year_from: str | None,
    year_to: str | None = "",
    record_id: str = "rec-1",
) -> dict[str, str | None]:
    return {
        "record_id": record_id,
        "organization": organization,
        "position": "",
        "year_from": year_from,
        "year_to": year_to,
        "reason_for_leaving": "",
    }


CALC_DATE = date(2026, 7, 23)


def test_non_overlapping_periods_sum() -> None:
    result = calculate_employment_tenure(
        [
            _record(organization="A", year_from="2020-01-01", year_to="2020-12-31"),
            _record(organization="B", year_from="2021-01-01", year_to="2021-12-31"),
        ],
        calculation_date=CALC_DATE,
    )
    assert result.arithmetic_sum_days == 729
    assert result.overlap_excluded_days == 0
    assert result.total_days == 729


def test_partially_overlapping_periods() -> None:
    result = calculate_employment_tenure(
        [
            _record(organization="A", year_from="2020-01-01", year_to="2020-12-31"),
            _record(organization="B", year_from="2020-07-01", year_to="2021-06-30"),
        ],
        calculation_date=CALC_DATE,
    )
    assert result.arithmetic_sum_days == 729
    assert result.overlap_excluded_days == 183
    assert result.total_days == 546


def test_nested_period_excludes_inner_overlap() -> None:
    result = calculate_employment_tenure(
        [
            _record(organization="Outer", year_from="2018-01-01", year_to="2022-12-31"),
            _record(organization="Inner", year_from="2019-06-01", year_to="2021-05-31"),
        ],
        calculation_date=CALC_DATE,
    )
    assert result.arithmetic_sum_days == 2555
    assert result.total_days == 1825
    assert result.overlap_excluded_days == 730
    assert result.records[1].overlaps_other is True


def test_identical_periods_count_once() -> None:
    result = calculate_employment_tenure(
        [
            _record(organization="A", year_from="2020-01-01", year_to="2020-12-31"),
            _record(organization="B", year_from="2020-01-01", year_to="2020-12-31"),
        ],
        calculation_date=CALC_DATE,
    )
    assert result.arithmetic_sum_days == 730
    assert result.overlap_excluded_days == 365
    assert result.total_days == 365
    assert all(row.overlaps_other for row in result.records if row.included)


def test_open_ended_period_uses_calculation_date() -> None:
    result = calculate_employment_tenure(
        [_record(organization="Current", year_from="2024-01-01")],
        calculation_date=CALC_DATE,
    )
    assert result.records[0].is_open_ended is True
    assert result.records[0].days == 934
    assert result.total_days == 934


def test_missing_start_is_excluded_with_warning() -> None:
    result = calculate_employment_tenure(
        [_record(organization="Broken", year_from="", year_to="2020-12-31")],
        calculation_date=CALC_DATE,
    )
    assert result.records[0].included is False
    assert result.records[0].warning == MISSING_START_WARNING
    assert result.total_days == 0


def test_end_before_start_is_excluded_with_warning() -> None:
    result = calculate_employment_tenure(
        [_record(organization="Broken", year_from="2022-01-01", year_to="2021-01-01")],
        calculation_date=CALC_DATE,
    )
    assert result.records[0].included is False
    assert result.records[0].warning == END_BEFORE_START_WARNING
    assert result.total_days == 0


def test_control_example_on_2026_07_23() -> None:
    result = calculate_employment_tenure(
        [
            _record(organization="R1", record_id="r1", year_from="2005-06-18", year_to="2008-09-01"),
            _record(organization="R2", record_id="r2", year_from="2007-07-19", year_to="2010-04-16"),
            _record(organization="R3", record_id="r3", year_from="2010-04-16", year_to="2026-07-23"),
            _record(organization="R4", record_id="r4", year_from="2014-09-17", year_to=""),
        ],
        calculation_date=CALC_DATE,
    )
    assert [row.days for row in result.records if row.included] == [1171, 1002, 5942, 4327]
    assert result.arithmetic_sum_days == 12442
    assert result.overlap_excluded_days == 4737
    assert result.total_days == 7705
    assert result.decimal_years == 21.1
    assert result.records[0].overlaps_other is True
    assert result.records[1].overlaps_other is True
    assert result.records[2].overlaps_other is True
    assert result.records[3].overlaps_other is True


def test_merge_employment_intervals() -> None:
    merged = merge_employment_intervals(
        [
            (date(2020, 1, 1), date(2020, 6, 30)),
            (date(2020, 6, 30), date(2020, 12, 31)),
        ]
    )
    assert merged == [(date(2020, 1, 1), date(2020, 12, 31))]


def test_accepts_pydantic_like_records() -> None:
    class FakeRecord:
        def model_dump(self) -> dict[str, str | None]:
            return {
                "record_id": "fake-1",
                "organization": "A",
                "position": "",
                "year_from": "1993-09-01",
                "year_to": "1994-07-25",
                "reason_for_leaving": "",
            }

    result = calculate_employment_tenure([FakeRecord()], calculation_date=CALC_DATE)
    assert result.records[0].included is True
    assert result.records[0].days == 327
    assert result.records[0].record_id == "fake-1"


def test_tenure_api_accepts_ru_dates_and_pydantic_models() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/intake/employment-tenure/calculate",
        json={
            "records": [
                {
                    "record_id": "api-1",
                    "organization": "Клиника",
                    "position": "",
                    "year_from": "01.09.1993",
                    "year_to": "25.07.1994",
                    "reason_for_leaving": "",
                }
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["records"][0]["included"] is True
    assert body["records"][0]["days"] == 327
    assert body["total_days"] == 327
