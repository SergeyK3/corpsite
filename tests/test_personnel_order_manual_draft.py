from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_order_manual_draft_service import create_manual_draft
from app.services.personnel_orders_command_service import PersonnelOrderConflictError
from app.services.personnel_orders_query_service import PersonnelOrderValidationError
from app.directory.personnel_orders_schemas import PersonnelOrderManualDraftCreateIn
from pydantic import ValidationError


def test_manual_draft_has_one_item_and_no_hr_consequences(seed):
    number = f"MANUAL-{uuid4().hex[:10]}"
    actor = int(seed["initiator_user_id"])
    with engine.connect() as conn:
        employee_id = int(conn.execute(text("SELECT employee_id FROM employees ORDER BY employee_id LIMIT 1")).scalar_one())
        before_events = int(conn.execute(text("SELECT count(*) FROM employee_events")).scalar_one())
        before_assignments = int(conn.execute(text("SELECT count(*) FROM person_assignments")).scalar_one())
    try:
        result = create_manual_draft(created_by=actor, order_number=number, order_date=date(2026, 9, 25), source_title="Қолмен енгізілген бұйрық", source_title_locale="kk", item_type_code="TRANSFER", employee_id=employee_id, effective_date=date(2026, 10, 1))
        assert result == {"order_id": result["order_id"], "order_number": number, "order_type_code": "TRANSFER", "status": "DRAFT", "source_mode": "MANUAL", "document_revision": 1, "document_review_state": "NEEDS_REVIEW"}
        with engine.connect() as conn:
            order = conn.execute(text("SELECT order_type_code,status,source_mode,source_title,source_title_locale,document_revision FROM personnel_orders WHERE order_id=:id"), {"id": result["order_id"]}).mappings().one()
            item = conn.execute(text("SELECT item_number,item_type_code,employee_id,effective_date FROM personnel_order_items WHERE order_id=:id"), {"id": result["order_id"]}).mappings().one()
            assert dict(order) == {"order_type_code": "TRANSFER", "status": "DRAFT", "source_mode": "MANUAL", "source_title": "Қолмен енгізілген бұйрық", "source_title_locale": "kk", "document_revision": 1}
            assert item["item_number"] == 1 and item["item_type_code"] == "TRANSFER" and item["employee_id"] == employee_id and item["effective_date"] == date(2026, 10, 1)
            assert int(conn.execute(text("SELECT count(*) FROM employee_events")).scalar_one()) == before_events
            assert int(conn.execute(text("SELECT count(*) FROM person_assignments")).scalar_one()) == before_assignments
        with pytest.raises(PersonnelOrderConflictError):
            create_manual_draft(created_by=actor, order_number=number, order_date=date(2026, 9, 25), source_title="x", source_title_locale="ru", item_type_code="TRANSFER", employee_id=employee_id, effective_date=date(2026, 10, 1))
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM personnel_order_evidence_scopes WHERE order_id IN (SELECT order_id FROM personnel_orders WHERE order_number=:number)"), {"number": number})
            conn.execute(text("DELETE FROM personnel_order_items WHERE order_id IN (SELECT order_id FROM personnel_orders WHERE order_number=:number)"), {"number": number})
            conn.execute(text("DELETE FROM personnel_orders WHERE order_number=:number"), {"number": number})


def test_manual_draft_requires_all_typed_fields_and_rejects_unknown_employee(seed):
    with pytest.raises(ValidationError):
        PersonnelOrderManualDraftCreateIn(order_number="1", order_date=date.today(), source_title="x", source_title_locale="kk", item_type_code="HIRE", employee_id=1)
    number = f"MANUAL-BAD-{uuid4().hex[:8]}"
    with engine.connect() as conn:
        before = int(conn.execute(text("SELECT count(*) FROM personnel_orders WHERE order_number=:number"), {"number": number}).scalar_one())
    with pytest.raises(PersonnelOrderValidationError, match="EMPLOYEE_NOT_FOUND"):
        create_manual_draft(created_by=int(seed["initiator_user_id"]), order_number=number, order_date=date(2026, 9, 25), source_title="x", source_title_locale="ru", item_type_code="HIRE", employee_id=999999999, effective_date=date(2026, 10, 1))
    with engine.connect() as conn:
        assert int(conn.execute(text("SELECT count(*) FROM personnel_orders WHERE order_number=:number"), {"number": number}).scalar_one()) == before


def test_manual_draft_schema_forbids_raw_payload():
    with pytest.raises(ValidationError):
        PersonnelOrderManualDraftCreateIn(order_number="1", order_date=date(2026, 9, 25), source_title="x", source_title_locale="ru", item_type_code="HIRE", employee_id=1, effective_date=date(2026, 10, 1), payload={})
