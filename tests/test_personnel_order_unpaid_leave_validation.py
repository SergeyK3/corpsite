from datetime import date

import pytest

from app.services.personnel_orders_command_service import (
    PersonnelOrderValidationError,
    _validate_leave_draft_item,
)


def _payload(days: int) -> dict[str, object]:
    return {
        "leave_start": "2026-08-03",
        "leave_end": "2026-08-12",
        "leave_days": days,
    }


def test_unpaid_leave_days_must_match_the_inclusive_period() -> None:
    _validate_leave_draft_item(
        item_type_code="LEAVE.UNPAID.GRANT",
        employee_id=1,
        effective_date=date(2026, 8, 3),
        period_start=date(2026, 8, 3),
        period_end=date(2026, 8, 12),
        payload=_payload(10),
    )

    with pytest.raises(PersonnelOrderValidationError, match="inclusive leave period days"):
        _validate_leave_draft_item(
            item_type_code="LEAVE.UNPAID.GRANT",
            employee_id=1,
            effective_date=date(2026, 8, 3),
            period_start=date(2026, 8, 3),
            period_end=date(2026, 8, 12),
            payload=_payload(9),
        )
