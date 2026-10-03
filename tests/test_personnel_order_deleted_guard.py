"""Unit coverage for the common soft-deleted personnel-order write guard."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from pathlib import Path

from app.directory.personnel_orders_routes import _conflict_http409
from app.services.personnel_orders_command_service import (
    PersonnelOrderDeletedError,
    require_active_personnel_order,
    require_order_row_not_deleted,
)


class _Result:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _Connection:
    def __init__(self, row):
        self.row = row
        self.statements = []

    def execute(self, statement, params):
        self.statements.append((str(statement), params))
        return _Result(self.row)


def test_deleted_order_guard_stops_before_downstream_write_and_locks_when_requested() -> None:
    conn = _Connection({"deleted_at": "2026-10-03T12:00:00+00:00"})

    with pytest.raises(PersonnelOrderDeletedError) as raised:
        require_active_personnel_order(conn, 73, lock=True)

    assert raised.value.code == "PERSONNEL_ORDER_DELETED"
    assert raised.value.message == "Приказ удалён из рабочего контура"
    assert len(conn.statements) == 1
    assert "FOR UPDATE" in conn.statements[0][0]


def test_active_order_passes_common_guard_and_existing_row_guard_has_same_contract() -> None:
    conn = _Connection({"deleted_at": None})
    require_active_personnel_order(conn, 74, lock=False)
    require_order_row_not_deleted({"order_id": 74, "deleted_at": None})

    with pytest.raises(PersonnelOrderDeletedError):
        require_order_row_not_deleted({"order_id": 74, "deleted_at": object()})


def test_deleted_order_has_one_stable_route_mapping() -> None:
    with pytest.raises(HTTPException) as raised:
        raise _conflict_http409(PersonnelOrderDeletedError())

    assert raised.value.status_code == 409
    assert raised.value.detail == {
        "code": "PERSONNEL_ORDER_DELETED",
        "message": "Приказ удалён из рабочего контура",
    }


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/services/personnel_order_document_header_service.py",
        "app/services/personnel_order_document_item_service.py",
        "app/services/personnel_order_document_review_service.py",
        "app/services/personnel_order_acknowledgement_service.py",
        "app/services/personnel_orders_apply_service.py",
        "app/services/personnel_orders_cancel_service.py",
        "app/services/personnel_orders_archive_service.py",
        "app/services/personnel_orders_void_service.py",
        "app/services/personnel_order_template_application_service.py",
    ],
)
def test_every_non_command_mutation_service_uses_the_common_deleted_order_guard(relative_path: str) -> None:
    """Keep a new writer from bypassing the fail-closed common contract."""
    source = (Path(__file__).parents[1] / relative_path).read_text(encoding="utf-8")
    assert "require_active_personnel_order" in source
