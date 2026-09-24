from app.services.personnel_orders_editorial.mapper import build_item_ctx
from app.services.personnel_orders_editorial.generators import generate_item_body


def test_multiperson_item_contexts_keep_assignment_and_source_name_isolated():
    items = [
        {"item_id": 30, "item_number": 3, "item_type_code": "HIRE", "effective_date": "2026-04-16", "payload": {"source_employee_name": "Third", "assignment": {"unit": {"ru": "U3"}, "position": {"ru": "P3"}, "rate": "0.5"}}},
        {"item_id": 10, "item_number": 1, "item_type_code": "HIRE", "effective_date": "2026-04-16", "payload": {"source_employee_name": "First", "assignment": {"unit": {"ru": "U1"}, "position": {"ru": "P1"}, "rate": "1.0"}}},
        {"item_id": 20, "item_number": 2, "item_type_code": "HIRE", "effective_date": "2026-04-16", "payload": {"source_employee_name": "Second", "assignment": {"unit": {"ru": "U2"}, "position": {"ru": "P2"}, "rate": "0.75"}}},
    ]
    ordered = sorted(items, key=lambda item: (item["item_number"], item["item_id"]))
    contexts = [build_item_ctx(item, None) for item in ordered]
    assert [context["employee_name"] for context in contexts] == ["First", "Second", "Third"]
    assert [context["org_unit_name"]["ru"] for context in contexts] == ["U1", "U2", "U3"]
    assert [context["position_name"]["ru"] for context in contexts] == ["P1", "P2", "P3"]
    assert [context["rate"] for context in contexts] == ["1.0", "0.75", "0.5"]
    assert "Second" in generate_item_body("ru", contexts[1])["generated_text"]
