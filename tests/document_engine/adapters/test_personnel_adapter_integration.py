# tests/document_engine/adapters/test_personnel_adapter_integration.py
"""Integration: PersonnelReadAdapter wiring (UDE-008)."""
from __future__ import annotations

from app.document_engine.adapters.personnel.read_adapter import PersonnelReadAdapter
from app.document_engine.value_objects.lifecycle import DocumentLifecycleState
from tests.document_engine.adapters._fixtures import (
    synthetic_detail,
    synthetic_editorial_state,
)


def test_from_order_id_wires_po_read_services(monkeypatch) -> None:
    detail = synthetic_detail()
    editorial = synthetic_editorial_state()

    monkeypatch.setattr(
        "app.services.personnel_orders_query_service.get_personnel_order",
        lambda order_id: detail,
    )
    monkeypatch.setattr(
        "app.document_engine.adapters.personnel.read_adapter.fetch_order_supplement",
        lambda order_id: {"void_kind": "CANCEL"},
    )
    monkeypatch.setattr(
        "app.services.personnel_orders_editorial.service.get_editorial_state",
        lambda order_id: editorial,
    )
    monkeypatch.setattr(
        "app.services.personnel_order_lifecycle_audit_service.list_personnel_order_lifecycle_audit",
        lambda order_id, limit, offset: {"items": [], "total": 0, "limit": limit, "offset": offset},
    )

    bundle = PersonnelReadAdapter.from_order_id(
        1001,
        include_editorial=True,
        include_audit=True,
    )
    assert bundle.document.lifecycle_state == DocumentLifecycleState.DRAFT
    assert bundle.document.void_kind is not None
    assert len(bundle.locale_blocks) == 3
    assert bundle.audit_events == ()
