"""Saved HIRE orders render the approved KK form from their own snapshot."""
from datetime import date

from app.services.personnel_order_template_application_service import _document_form_kk
from app.services.personnel_orders_editorial.generators import generate_item_body
from app.services.personnel_orders_editorial.mapper import build_item_ctx


def test_saved_hire_uses_kk_document_form_instead_of_catalog_title():
    payload = {
        "source_employee_name": "Наша Маша",
        "source_org_unit_name": "Хирургия 2",
        "org_unit_title_kk": "№2 хирургия бөлімшесі",
        "source_position_name": "Буфетчица",
        "position_title_kk": "Буфетші",
        "position_document_possessive_kk": "буфетшісі",
        "employment_rate": 1,
    }
    assert _document_form_kk(payload, "position.document_possessive_kk") == "буфетшісі"
    ctx = build_item_ctx({"item_type_code": "HIRE", "payload": payload,
                          "effective_date": date(2026, 11, 26)}, None)
    body = generate_item_body("kk", ctx)["generated_text"]
    assert "буфетшісі лауазымына" in body
    assert "Буфетші лауазымына" not in body


def test_nested_document_form_takes_precedence_over_legacy_snapshot():
    payload = {
        "position_document_possessive_kk": "ескі нұсқа",
        "document_forms_kk": {"position_document_possessive_kk": "буфетшісі"},
    }
    assert _document_form_kk(payload, "position.document_possessive_kk") == "буфетшісі"
    ctx = build_item_ctx({"item_type_code": "HIRE", "payload": payload}, None)
    assert ctx["position_document_possessive_kk"] == "буфетшісі"
