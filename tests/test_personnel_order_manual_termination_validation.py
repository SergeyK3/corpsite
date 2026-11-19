"""Focused validation for manually created termination orders."""
from datetime import date

import pytest

from app.services import personnel_order_manual_draft_service as manual
from app.services.personnel_orders_query_service import PersonnelOrderValidationError


def prepare(monkeypatch, *, catalog_title: str, reason: str, picker_title: str = ""):
    monkeypatch.setattr(
        manual,
        "_selected_employee_payload",
        lambda *args, **kwargs: {"position_title_kk": catalog_title},
    )
    monkeypatch.setattr(manual, "apply_document_department", lambda conn, payload, context: payload)
    monkeypatch.setattr(
        manual,
        "apply_document_position",
        lambda conn, payload, context: {
            **payload,
            "position_title_kk": (context or {}).get("document_position_kk") or payload.get("position_title_kk"),
        },
    )
    return manual.prepare_manual_item_payload(
        object(),
        item_type_code="TERMINATION",
        employee_id=1,
        effective_date=date(2026, 11, 19),
        item_payload={"termination_reason": reason},
        document_subject_context={"document_position_kk": picker_title},
        capabilities={"job_catalog_supported": True},
    )


def test_termination_uses_confirmed_catalog_title_when_picker_title_is_blank(monkeypatch):
    result = prepare(monkeypatch, catalog_title="Дәрігер", reason="EMPLOYEE_INITIATIVE")
    assert result["position_title_kk"] == "Дәрігер"
    assert result["termination_reason"] == "EMPLOYEE_INITIATIVE"


def test_termination_requires_reason_and_kazakh_position_title(monkeypatch):
    with pytest.raises(PersonnelOrderValidationError, match="причину расторжения"):
        prepare(monkeypatch, catalog_title="Дәрігер", reason="  ")
    with pytest.raises(PersonnelOrderValidationError, match="должность на казахском языке"):
        prepare(monkeypatch, catalog_title="", reason="EMPLOYEE_INITIATIVE")
