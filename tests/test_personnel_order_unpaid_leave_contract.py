from datetime import date

import pytest

from app.services.personnel_order_unpaid_leave_contract import (
    UnpaidLeaveContractError,
    period_clause_kk,
    period_clause_ru,
    period_text,
    unpaid_leave_period,
)


def test_legacy_range_remains_readable_without_rewrite() -> None:
    payload = {"leave_start": "2026-07-13", "leave_end": "2026-07-15", "leave_days": 3}
    period = unpaid_leave_period(payload)
    assert period["legacy"] is True
    assert period["period_type"] == "CONTINUOUS_RANGE"
    assert period_text(period, "ru") == "с 13 июля 2026 года по 15 июля 2026 года включительно"


@pytest.mark.parametrize(
    ("payload", "kind", "text"),
    [
        ({"leave": {"period_type": "SINGLE_DAY", "start": "2026-07-07", "end": "2026-07-07", "days": 1}}, "SINGLE_DAY", "2026 жылғы 7 шілде"),
        ({"leave": {"period_type": "CONTINUOUS_RANGE", "start": "2026-07-13", "end": "2026-07-15", "days": 3}}, "CONTINUOUS_RANGE", "2026 жылғы 13 шілде мен 2026 жылғы 15 шілде аралығы"),
    ],
)
def test_new_period_types_render_locally(payload: dict, kind: str, text: str) -> None:
    period = unpaid_leave_period(payload)
    assert period["period_type"] == kind
    assert period_text(period, "kk") == text


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"leave": {"period_type": "SINGLE_DAY", "start": "2026-07-07", "end": "2026-07-07", "days": 1}}, "2026 жылғы 7 шілде күніне"),
        ({"leave": {"period_type": "CONTINUOUS_RANGE", "start": "2026-07-13", "end": "2026-07-15", "days": 3}}, "2026 жылғы 13 мен 15 шілде аралығында"),
    ],
)
def test_document_period_clause_kk(payload: dict, expected: str) -> None:
    assert period_clause_kk(unpaid_leave_period(payload)) == expected


@pytest.mark.parametrize("payload", [
    {"leave": {"period_type": "SINGLE_DAY", "start": "2026-07-07", "end": "2026-07-08", "days": 1}},
    {"leave": {"period_type": "CONTINUOUS_RANGE", "start": "2026-07-17", "end": "2026-07-10", "days": 2}},
    {"leave": {"period_type": "SINGLE_DAY", "start": "2026-07-10", "end": "2026-07-10", "dates": ["2026-07-10"], "days": 1}},
])
def test_ambiguous_or_inconsistent_period_is_rejected(payload: dict) -> None:
    with pytest.raises(UnpaidLeaveContractError):
        unpaid_leave_period(payload)


def test_document_period_clause_ru() -> None:
    single = unpaid_leave_period({"leave": {"period_type": "SINGLE_DAY", "start": "2026-07-07", "end": "2026-07-07", "days": 1}})
    period = unpaid_leave_period({"leave": {"period_type": "CONTINUOUS_RANGE", "start": "2026-07-13", "end": "2026-07-17", "days": 5}})
    assert period_clause_ru(single) == "7 июля 2026 года"
    assert period_clause_ru(period) == "с 13 по 17 июля 2026 года включительно"
