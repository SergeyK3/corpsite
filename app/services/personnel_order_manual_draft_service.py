"""Create one typed MANUAL personnel-order draft without HR consequences."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_orders import PERSONNEL_ORDER_ITEM_TYPE_CODES, SOURCE_MODE_MANUAL
from app.services.personnel_order_document_header_service import duplicate_preview
from app.services.personnel_orders_command_service import PersonnelOrderConflictError
from app.services.personnel_orders_query_service import PersonnelOrderValidationError
from app.services.personnel_order_evidence_scope_service import create_personnel_order_evidence_scope_tx


def create_manual_draft(*, created_by: int, order_number: str, order_date: date, source_title: str, source_title_locale: str, item_type_code: str, employee_id: int, effective_date: date) -> dict[str, Any]:
    number = str(order_number or "").strip()
    title = str(source_title or "").strip()
    if not number or not title:
        raise PersonnelOrderValidationError("Manual order number and source title are required.")
    if item_type_code not in PERSONNEL_ORDER_ITEM_TYPE_CODES:
        raise PersonnelOrderValidationError("Unsupported item type.")
    duplicate = duplicate_preview(order_number=number, order_date=order_date)
    if duplicate["blocking"]:
        raise PersonnelOrderConflictError("DUPLICATE_ORDER_NUMBER_DATE")
    with engine.begin() as conn:
        if not conn.execute(text("SELECT 1 FROM employees WHERE employee_id=:id"), {"id": employee_id}).first():
            raise PersonnelOrderValidationError("EMPLOYEE_NOT_FOUND")
        # Recheck inside the write transaction; browser preview is never authoritative.
        duplicate = duplicate_preview(order_number=number, order_date=order_date)
        if duplicate["blocking"]:
            raise PersonnelOrderConflictError("DUPLICATE_ORDER_NUMBER_DATE")
        order_id = int(conn.execute(text("""
            INSERT INTO personnel_orders(order_number,order_date,order_type_code,status,source_mode,source_title,source_title_locale,storage_json,created_by)
            VALUES(:number,:order_date,:item_type,'DRAFT',:source_mode,:title,:locale,'{}'::jsonb,:created_by)
            RETURNING order_id
        """), {"number": number, "order_date": order_date, "item_type": item_type_code, "source_mode": SOURCE_MODE_MANUAL, "title": title, "locale": source_title_locale, "created_by": created_by}).scalar_one())
        conn.execute(text("""
            INSERT INTO personnel_order_items(order_id,item_number,item_type_code,item_status,employee_id,effective_date,payload)
            VALUES(:order_id,1,:item_type,'ACTIVE',:employee_id,:effective_date,'{}'::jsonb)
        """), {"order_id": order_id, "item_type": item_type_code, "employee_id": employee_id, "effective_date": effective_date})
        create_personnel_order_evidence_scope_tx(conn, order_id=order_id)
    return {"order_id": order_id, "order_number": number, "order_type_code": item_type_code, "status": "DRAFT", "source_mode": SOURCE_MODE_MANUAL, "document_revision": 1, "document_review_state": "NEEDS_REVIEW"}
