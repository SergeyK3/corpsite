from datetime import date

from app.services import personnel_orders_apply_service as service


def test_childcare_return_item_mapping_and_event_preserve_employee_snapshot(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        service,
        "_fetch_employee_snapshot",
        lambda _conn, _employee_id: {
            "employee_id": 7,
            "org_unit_id": 3,
            "position_id": 5,
            "employment_rate": 1.0,
            "is_active": True,
        },
    )
    monkeypatch.setattr(service, "_insert_employee_event", lambda _conn, **kwargs: captured.update(kwargs))

    assert service._resolve_event_types("RETURN_FROM_CHILDCARE_LEAVE", {}) == [
        "LEAVE.CHILDCARE.RETURN"
    ]
    service._apply_childcare_leave_return(
        object(),
        item={"item_id": 19, "employee_id": 7, "effective_date": date(2026, 9, 2)},
        order_id=11,
        order_ref="№11-К от 2026-09-01",
        created_by=1,
    )

    assert captured["event_type"] == "LEAVE.CHILDCARE.RETURN"
    assert captured["effective_date"] == date(2026, 9, 2)
    assert captured["order_id"] == 11
    assert captured["order_item_id"] == 19
    assert captured["from_org_unit_id"] == captured["to_org_unit_id"] == 3
    assert captured["from_position_id"] == captured["to_position_id"] == 5
    assert captured["from_rate"] == captured["to_rate"] == 1.0
