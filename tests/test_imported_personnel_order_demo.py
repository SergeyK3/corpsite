"""Isolated synthetic import correction and employee-card query scenario."""
from contextlib import nullcontext
from datetime import date
from uuid import uuid4

from sqlalchemy import text

from app.db.engine import engine
from app.services import personnel_order_document_header_service as headers
from app.services import personnel_orders_query_service as queries
from app.services.personnel_orders_command_service import register_personnel_order_tx


class _TransactionEngine:
    def __init__(self, connection):
        self.connection = connection

    def begin(self):
        return nullcontext(self.connection)

    def connect(self):
        return nullcontext(self.connection)


def test_imported_order_correction_keeps_quality_and_employee_link_in_both_statuses(seed, monkeypatch):
    actor = int(seed["initiator_user_id"])
    suffix = uuid4().hex[:8]
    technical = f"CSV-PILOT-{suffix}"
    official = "935 тест"
    with engine.connect() as conn:
        transaction = conn.begin()
        monkeypatch.setattr(headers, "engine", _TransactionEngine(conn))
        monkeypatch.setattr(queries, "engine", _TransactionEngine(conn))
        try:
            employee_id = int(conn.execute(text("""
                INSERT INTO employees(full_name, org_unit_id)
                VALUES ('Synthetic Demo Employee', :unit) RETURNING employee_id
            """), {"unit": seed["unit_id"]}).scalar_one())
            order_id = int(conn.execute(text("""
                INSERT INTO personnel_orders(order_number, order_date, order_type_code,
                    status, source_mode, created_by, storage_json)
                VALUES (:number, :day, 'HIRE', 'DRAFT', 'DIGITAL', :actor, '{}'::jsonb)
                RETURNING order_id
            """), {"number": technical, "day": date(2026, 11, 12), "actor": actor}).scalar_one())
            conn.execute(text("INSERT INTO personnel_order_evidence_scopes(order_id) VALUES (:id)"), {"id": order_id})
            conn.execute(text("""
                INSERT INTO personnel_order_items(order_id, item_number, item_type_code,
                    employee_id, effective_date, payload)
                VALUES (:order_id, 1, 'HIRE', :employee_id, :day, '{}'::jsonb)
            """), {"order_id": order_id, "employee_id": employee_id, "day": date(2026, 11, 12)})

            for status in ("SIGNED", "REGISTERED"):
                scenario = conn.begin_nested()
                try:
                    register_personnel_order_tx(conn, order_id=order_id, target_status=status)
                    assert queries.list_personnel_orders(employee_id=employee_id, status=status, record_quality="ALL")["total"] == 1
                    assert queries.list_personnel_orders(employee_id=employee_id, status=status, record_quality="WORKING")["total"] == 0
                    assert headers.duplicate_preview(order_number=official, order_date=date(2026, 11, 12), order_id=order_id)["blocking"] is False

                    result = headers.patch_document_header(
                        order_id=order_id, expected_document_revision=1,
                        order_number=official, order_date=date(2026, 11, 12),
                        source_title=None, source_title_locale=None,
                        reason_code="ORIGINAL_VERIFIED", reason_text="Synthetic original checked",
                        actor_user_id=actor,
                    )
                    assert result["no_op"] is False
                    detail = queries.get_personnel_order(order_id)
                    assert detail["order"]["status"] == status
                    assert detail["order"]["order_number"] == official
                    assert detail["order"]["storage_json"]["import_source_order_number"] == technical
                    assert detail["order"]["storage_json"]["technical_record"] is True
                    assert detail["order"]["storage_json"]["record_quality"] == "TECHNICAL_RECORD"
                    assert queries.list_personnel_orders(employee_id=employee_id, status=status, record_quality="ALL")["items"][0]["order_id"] == order_id
                    assert queries.list_personnel_orders(employee_id=employee_id, status=status, record_quality="TECHNICAL")["total"] == 1
                    assert queries.list_personnel_orders(employee_id=employee_id, status=status, record_quality="WORKING")["total"] == 0
                    assert conn.execute(text("SELECT count(*) FROM employee_events WHERE order_id=:id"), {"id": order_id}).scalar_one() == 0
                    audit = conn.execute(text("SELECT reason_code, metadata_json FROM personnel_order_lifecycle_audit WHERE order_id=:id AND action='HEADER_UPDATED'"), {"id": order_id}).mappings().one()
                    assert audit["reason_code"] == "ORIGINAL_VERIFIED"
                    assert audit["metadata_json"]["before"]["order_number"] == technical
                finally:
                    scenario.rollback()
        finally:
            transaction.rollback()
