"""Typed document-only correction of active personnel-order items."""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Mapping, Optional

from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_orders import LIFECYCLE_AUDIT_ACTION_DOCUMENT_REOPENED, LIFECYCLE_AUDIT_ACTION_ITEM_UPDATED, PERSONNEL_ORDER_ITEM_TYPE_CODES
from app.services.personnel_order_document_review_service import PersonnelOrderDocumentReviewConflictError
from app.services.personnel_order_lifecycle_audit_service import append_personnel_order_lifecycle_audit
from app.services.personnel_orders_editorial.generation_service import generate_editorial
from app.services.personnel_orders_query_service import PersonnelOrderNotFoundError


def _safe_context(payload: Mapping[str, Any], context: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    out = dict(payload)
    for key, value in (context or {}).items():
        text_value = str(value or "").strip()
        if key == "position_name": out["source_position_name"] = text_value
        elif key == "org_unit_name": out["source_org_unit_name"] = text_value
        elif key == "specialty": out["document_specialty"] = text_value or None
        elif key == "rate": out["document_rate"] = text_value or None
    return out


def _typed_row(row: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["effective_date"] = item["effective_date"].isoformat() if item.get("effective_date") else None
    return item


def list_document_items(*, order_id: int) -> dict[str, Any]:
    with engine.connect() as c:
        order = c.execute(text("SELECT document_revision FROM personnel_orders WHERE order_id=:id"), {"id": order_id}).mappings().one_or_none()
        if not order: raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")
        rows = c.execute(text("""
            SELECT poi.item_id, poi.item_number, poi.item_type_code, poi.employee_id,
              COALESCE(NULLIF(BTRIM(poi.payload ->> 'source_employee_name'), ''), e.full_name) AS employee_name,
              COALESCE(NULLIF(BTRIM(poi.payload ->> 'source_org_unit_name'), ''), ou.name) AS org_unit_name,
              COALESCE(NULLIF(BTRIM(poi.payload ->> 'source_position_name'), ''), pos.name) AS position_name,
              COALESCE(NULLIF(BTRIM(poi.payload ->> 'document_specialty'), ''), NULLIF(BTRIM(poi.payload #>> '{unresolved_subject,specialty}'), '')) AS specialty,
              NULLIF(BTRIM(poi.payload ->> 'document_rate'), '') AS rate,
              CASE WHEN poi.payload #>> '{unresolved_subject,needs_employee_link}' = 'true' THEN TRUE ELSE FALSE END AS needs_employee_link,
              poi.effective_date
            FROM personnel_order_items poi
            LEFT JOIN employees e ON e.employee_id=poi.employee_id
            LEFT JOIN org_units ou ON ou.unit_id=e.org_unit_id
            LEFT JOIN positions pos ON pos.position_id=e.position_id
            WHERE poi.order_id=:order_id AND poi.item_status='ACTIVE'
            ORDER BY poi.item_number, poi.item_id
        """), {"order_id": order_id}).mappings().all()
    return {"document_revision": int(order["document_revision"]), "items": [_typed_row(row) for row in rows]}


def patch_document_item(*, order_id: int, item_id: int, expected_document_revision: int, item_type_code: str, employee_id: Optional[int], effective_date: Optional[date], document_subject_context: Optional[Mapping[str, Any]], reason_code: Optional[str], reason_text: Optional[str], actor_user_id: int) -> dict[str, Any]:
    with engine.begin() as c:
        order = c.execute(text("SELECT order_id,status,order_type_code,document_revision FROM personnel_orders WHERE order_id=:id FOR UPDATE"), {"id": order_id}).mappings().one_or_none()
        if not order: raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")
        if int(order["document_revision"]) != expected_document_revision: raise PersonnelOrderDocumentReviewConflictError("DOCUMENT_REVISION_CONFLICT")
        if order["status"] in {"REGISTERED", "SIGNED"} and (not str(reason_code or "").strip() or not str(reason_text or "").strip()): raise ValueError("CORRECTION_REASON_REQUIRED")
        if item_type_code not in PERSONNEL_ORDER_ITEM_TYPE_CODES: raise ValueError("INVALID_ITEM_TYPE_CODE")
        item = c.execute(text("SELECT item_id,item_type_code,employee_id,effective_date,payload FROM personnel_order_items WHERE order_id=:order_id AND item_id=:item_id AND item_status='ACTIVE' FOR UPDATE"), {"order_id": order_id, "item_id": item_id}).mappings().one_or_none()
        if not item: raise ValueError("ACTIVE_ITEM_NOT_FOUND")
        employee = None
        if employee_id is not None:
            employee = c.execute(text("SELECT employee_id,full_name FROM employees WHERE employee_id=:id"), {"id": employee_id}).mappings().one_or_none()
            if employee is None: raise ValueError("EMPLOYEE_NOT_FOUND")
        old_payload = item["payload"] if isinstance(item["payload"], dict) else json.loads(item["payload"] or "{}")
        current_basis_type = c.execute(text("SELECT basis_type FROM personnel_order_item_bases WHERE order_item_id=:item_id"), {"item_id": item_id}).scalar_one_or_none()
        new_payload = _safe_context(old_payload, document_subject_context)
        if employee is not None:
            # The name is server-derived for the document context; the browser
            # still sends only the selected internal employee_id.
            new_payload["source_employee_name"] = str(employee["full_name"] or "").strip()
        requested_basis_type = str((document_subject_context or {}).get("basis_type") or "").strip().upper()
        before = {"item_type_code": item["item_type_code"], "employee_id": item["employee_id"], "effective_date": item["effective_date"].isoformat() if item["effective_date"] else None, "document_subject_context": {"position_name": old_payload.get("source_position_name"), "org_unit_name": old_payload.get("source_org_unit_name"), "specialty": old_payload.get("document_specialty"), "rate": old_payload.get("document_rate"), "basis_type": current_basis_type}}
        after = {"item_type_code": item_type_code, "employee_id": employee_id, "effective_date": effective_date.isoformat() if effective_date else None, "document_subject_context": {"position_name": new_payload.get("source_position_name"), "org_unit_name": new_payload.get("source_org_unit_name"), "specialty": new_payload.get("document_specialty"), "rate": new_payload.get("document_rate"), "basis_type": requested_basis_type or current_basis_type}}
        if before == after: return {"no_op": True, "resulting_document_revision": int(order["document_revision"]), "audit_event_ids": []}
        c.execute(text("UPDATE personnel_order_items SET item_type_code=:type,employee_id=:employee,effective_date=:date,payload=CAST(:payload AS jsonb) WHERE item_id=:id"), {"type": item_type_code, "employee": employee_id, "date": effective_date, "payload": json.dumps(new_payload, ensure_ascii=False), "id": item_id})
        if requested_basis_type:
            c.execute(text("UPDATE personnel_order_item_bases SET basis_type=:basis_type WHERE order_item_id=:item_id"), {"basis_type": requested_basis_type, "item_id": item_id})
        types = c.execute(text("SELECT DISTINCT item_type_code FROM personnel_order_items WHERE order_id=:id AND item_status='ACTIVE'"), {"id": order_id}).scalars().all()
        header_type = types[0] if len(types) == 1 else "COMPOSITE"; revision = int(order["document_revision"]) + 1
        c.execute(text("UPDATE personnel_orders SET order_type_code=:type,document_revision=:revision WHERE order_id=:id"), {"type": header_type, "revision": revision, "id": order_id})
        audit_id = append_personnel_order_lifecycle_audit(c, order_id=order_id, action=LIFECYCLE_AUDIT_ACTION_ITEM_UPDATED, previous_status=order["status"], new_status=order["status"], previous_void_kind=None, new_void_kind=None, actor_user_id=actor_user_id, reason_code=reason_code, reason_text=reason_text, metadata_json={"item_id": item_id, "before": before, "after": after, "expected_document_revision": expected_document_revision, "resulting_document_revision": revision, "header_type_before": order["order_type_code"], "header_type_after": header_type})
        latest = c.execute(text("SELECT action FROM personnel_order_lifecycle_audit WHERE order_id=:id AND action IN ('DOCUMENT_CONFIRMED','DOCUMENT_REOPENED') ORDER BY created_at DESC,id DESC LIMIT 1"), {"id": order_id}).scalar()
        audit_ids = [audit_id] if audit_id else []
        if latest == "DOCUMENT_CONFIRMED":
            reopened = append_personnel_order_lifecycle_audit(c, order_id=order_id, action=LIFECYCLE_AUDIT_ACTION_DOCUMENT_REOPENED, previous_status=order["status"], new_status=order["status"], previous_void_kind=None, new_void_kind=None, actor_user_id=actor_user_id, reason_code="ITEM_CHANGED", reason_text="Document item changed", metadata_json={"resulting_document_revision": revision})
            if reopened: audit_ids.append(reopened)
        # Older reconstructed orders may predate evidence scopes.  The scope is
        # internal generation concurrency state, not document content.
        c.execute(text("INSERT INTO personnel_order_evidence_scopes(order_id) VALUES (:id) ON CONFLICT (order_id) DO NOTHING"), {"id": order_id})
        generate_editorial(order_id, user_id=actor_user_id, conn=c, scope={"item_id": item_id}, allow_document_correction=True)
    return {"no_op": False, "resulting_document_revision": revision, "header_type_code": header_type, "document_review_state": "NEEDS_REVIEW" if len(audit_ids) > 1 else None, "audit_event_ids": audit_ids}
