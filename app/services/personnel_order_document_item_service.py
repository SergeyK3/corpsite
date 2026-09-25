"""Typed document-only correction of existing active personnel order items."""
from __future__ import annotations
from datetime import date
from typing import Any, Optional
from sqlalchemy import text
from app.db.engine import engine
from app.db.models.personnel_orders import (
    LIFECYCLE_AUDIT_ACTION_DOCUMENT_REOPENED,
    LIFECYCLE_AUDIT_ACTION_ITEM_UPDATED,
    PERSONNEL_ORDER_ITEM_TYPE_CODES,
)
from app.services.personnel_order_lifecycle_audit_service import append_personnel_order_lifecycle_audit
from app.services.personnel_order_document_review_service import PersonnelOrderDocumentReviewConflictError
from app.services.personnel_orders_query_service import PersonnelOrderNotFoundError


def list_document_items(*, order_id: int) -> dict[str, Any]:
  """Return only fields that the typed item-correction UI is allowed to see."""
  with engine.connect() as c:
    order = c.execute(text("SELECT document_revision FROM personnel_orders WHERE order_id=:id"), {"id": order_id}).mappings().one_or_none()
    if not order:
      raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")
    rows = c.execute(text("""
      SELECT poi.item_id, poi.item_number, poi.item_type_code, poi.employee_id,
             e.full_name AS employee_name, poi.effective_date
      FROM personnel_order_items poi
      LEFT JOIN employees e ON e.employee_id = poi.employee_id
      WHERE poi.order_id=:order_id AND poi.item_status='ACTIVE'
      ORDER BY poi.item_number, poi.item_id
    """), {"order_id": order_id}).mappings().all()
  return {"document_revision": int(order["document_revision"]), "items": [
    {**dict(row), "effective_date": row["effective_date"].isoformat() if row["effective_date"] else None}
    for row in rows
  ]}

def patch_document_item(*,order_id:int,item_id:int,expected_document_revision:int,item_type_code:str,employee_id:Optional[int],effective_date:Optional[date],reason_code:Optional[str],reason_text:Optional[str],actor_user_id:int)->dict[str,Any]:
  with engine.begin() as c:
    order=c.execute(text("SELECT order_id,status,order_type_code,document_revision FROM personnel_orders WHERE order_id=:id FOR UPDATE"),{"id":order_id}).mappings().one_or_none()
    if not order: raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")
    if int(order["document_revision"])!=expected_document_revision: raise PersonnelOrderDocumentReviewConflictError("DOCUMENT_REVISION_CONFLICT")
    if order["status"] in {"REGISTERED","SIGNED"} and (not str(reason_code or "").strip() or not str(reason_text or "").strip()): raise ValueError("CORRECTION_REASON_REQUIRED")
    if item_type_code not in PERSONNEL_ORDER_ITEM_TYPE_CODES: raise ValueError("INVALID_ITEM_TYPE_CODE")
    item=c.execute(text("SELECT item_id,item_type_code,employee_id,effective_date FROM personnel_order_items WHERE order_id=:order_id AND item_id=:item_id AND item_status='ACTIVE' FOR UPDATE"),{"order_id":order_id,"item_id":item_id}).mappings().one_or_none()
    if not item: raise ValueError("ACTIVE_ITEM_NOT_FOUND")
    before={k:(item[k].isoformat() if k=="effective_date" and item[k] else item[k]) for k in ("item_type_code","employee_id","effective_date")}; after={"item_type_code":item_type_code,"employee_id":employee_id,"effective_date":effective_date.isoformat() if effective_date else None}
    if before==after:return {"no_op":True,"resulting_document_revision":int(order["document_revision"]),"audit_event_ids":[]}
    if employee_id is not None and not c.execute(text("SELECT 1 FROM employees WHERE employee_id=:id"),{"id":employee_id}).first():raise ValueError("EMPLOYEE_NOT_FOUND")
    c.execute(text("UPDATE personnel_order_items SET item_type_code=:t,employee_id=:e,effective_date=:d WHERE item_id=:id"),{"t":item_type_code,"e":employee_id,"d":effective_date,"id":item_id})
    types=c.execute(text("SELECT DISTINCT item_type_code FROM personnel_order_items WHERE order_id=:id AND item_status='ACTIVE'"),{"id":order_id}).scalars().all(); header_type=types[0] if len(types)==1 else "COMPOSITE"; rev=int(order["document_revision"])+1
    c.execute(text("UPDATE personnel_orders SET order_type_code=:t,document_revision=:r WHERE order_id=:id"),{"t":header_type,"r":rev,"id":order_id})
    aid=append_personnel_order_lifecycle_audit(c,order_id=order_id,action=LIFECYCLE_AUDIT_ACTION_ITEM_UPDATED,previous_status=order["status"],new_status=order["status"],previous_void_kind=None,new_void_kind=None,actor_user_id=actor_user_id,reason_code=reason_code,reason_text=reason_text,metadata_json={"item_id":item_id,"before":before,"after":after,"expected_document_revision":expected_document_revision,"resulting_document_revision":rev,"header_type_before":order["order_type_code"],"header_type_after":header_type})
    latest=c.execute(text("SELECT action FROM personnel_order_lifecycle_audit WHERE order_id=:id AND action IN ('DOCUMENT_CONFIRMED','DOCUMENT_REOPENED') ORDER BY created_at DESC,id DESC LIMIT 1"),{"id":order_id}).scalar()
    ids=[aid] if aid else []
    if latest=="DOCUMENT_CONFIRMED":
      reopened=append_personnel_order_lifecycle_audit(c,order_id=order_id,action=LIFECYCLE_AUDIT_ACTION_DOCUMENT_REOPENED,previous_status=order["status"],new_status=order["status"],previous_void_kind=None,new_void_kind=None,actor_user_id=actor_user_id,reason_code="ITEM_CHANGED",reason_text="Document item changed",metadata_json={"resulting_document_revision":rev})
      if reopened: ids.append(reopened)
  return {"no_op":False,"resulting_document_revision":rev,"header_type_code":header_type,"document_review_state":"NEEDS_REVIEW" if len(ids)>1 else None,"audit_event_ids":ids}
