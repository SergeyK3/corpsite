"""Typed, document-only correction of personnel-order header requisites."""
from __future__ import annotations
import re
from datetime import date
from typing import Any, Optional
from contextlib import nullcontext
from sqlalchemy import text
from app.db.engine import engine
from app.db.personnel_order_header_uniqueness import NUMBER_KEY_SQL
from app.db.models.personnel_orders import LIFECYCLE_AUDIT_ACTION_DOCUMENT_REOPENED, LIFECYCLE_AUDIT_ACTION_HEADER_UPDATED
from app.services.personnel_order_lifecycle_audit_service import append_personnel_order_lifecycle_audit
from app.services.personnel_orders_query_service import PersonnelOrderNotFoundError
from app.services.personnel_orders_command_service import require_active_personnel_order, PersonnelOrderConflictError
from app.services.personnel_order_document_review_service import PersonnelOrderDocumentReviewConflictError, get_document_review

def _number(value: str) -> str:
    return re.sub(r"[‐‑‒–—―]", "-", " ".join(str(value or "").split())).upper()

class PersonnelOrderDuplicateError(PersonnelOrderConflictError):
    def __init__(self, duplicate):
        self.duplicate = duplicate
        conflicts = [r for r in duplicate['candidates'] if r.get('is_conflict')]
        details = '; '.join(f"№ {r['order_number']} от {r['order_date']} (ID {r['order_id']})" for r in conflicts)
        self.message = 'Уже существует приказ с такими же номером и датой: ' + details + '.'
        super().__init__('DUPLICATE_ORDER_NUMBER_DATE')


def duplicate_preview(*, order_number: str, order_date: Optional[date], order_id: Optional[int] = None, conn=None) -> dict[str, Any]:
    with nullcontext(conn) if conn is not None else engine.connect() as connection:
        rows=connection.execute(text(f"""SELECT po.order_id,po.order_number,po.order_date,po.order_type_code,po.status,
          CASE WHEN (po.storage_json->>'technical_record'='true' AND upper(po.storage_json->>'record_quality') IN ('TECHNICAL','TECHNICAL_RECORD'))
            OR upper(po.order_number) LIKE 'PERSONNEL-IMPORT-%' OR upper(po.order_number) LIKE 'CSV-PILOT-%' THEN 'TECHNICAL' ELSE 'WORKING' END AS record_quality
          FROM personnel_orders po WHERE po.deleted_at IS NULL AND po.order_id <> COALESCE(:id,-1)
          AND {NUMBER_KEY_SQL.replace('order_number','po.order_number')}=:number ORDER BY po.order_id"""), {"id":order_id,"number":_number(order_number)}).mappings().all()
    candidates=[{"order_id":int(r["order_id"]),"order_number":r["order_number"],"order_date":r["order_date"].isoformat() if r["order_date"] else None,"order_type_code":r["order_type_code"],"status":r["status"],"record_quality":r['record_quality'],"is_conflict":bool(order_date and r['order_date']==order_date),"can_open":True} for r in rows]
    blocking=bool(order_date and any(r["order_date"]==order_date for r in rows))
    return {"blocking":blocking,"warnings":(["SAME_NUMBER_DIFFERENT_DATE"] if rows and not blocking else []),"candidates":candidates}

def patch_document_header(*, order_id:int, expected_document_revision:int, order_number:str, order_date:Optional[date], source_title:Optional[str], source_title_locale:Optional[str], reason_code:Optional[str], reason_text:Optional[str], actor_user_id:int)->dict[str,Any]:
    with engine.begin() as conn:
        require_active_personnel_order(conn, order_id, lock=True)
        order=conn.execute(text("SELECT * FROM personnel_orders WHERE order_id=:id FOR UPDATE"),{"id":order_id}).mappings().one_or_none()
        if not order: raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")
        if int(order["document_revision"])!=expected_document_revision: raise PersonnelOrderDocumentReviewConflictError("DOCUMENT_REVISION_CONFLICT")
        registered=str(order["status"]) in {"REGISTERED","SIGNED"}
        if registered and (not str(reason_code or "").strip() or not str(reason_text or "").strip()): raise ValueError("CORRECTION_REASON_REQUIRED")
        duplicate=duplicate_preview(order_number=order_number,order_date=order_date,order_id=order_id,conn=conn)
        if duplicate["blocking"]: raise PersonnelOrderDuplicateError(duplicate)
        before={k:(order[k].isoformat() if k=="order_date" and order[k] else order[k]) for k in ("order_number","order_date","source_title","source_title_locale")}
        after={"order_number":order_number,"order_date":order_date.isoformat() if order_date else None,"source_title":source_title,"source_title_locale":source_title_locale}
        if before==after:
            return {"header":after,"resulting_document_revision":int(order["document_revision"]),"document_review_state":get_document_review(order_id)["state"],"duplicate":duplicate,"audit_event_ids":[],"no_op":True}
        next_revision=int(order["document_revision"])+1
        conn.execute(text("UPDATE personnel_orders SET order_number=:number,order_date=:date,source_title=:title,source_title_locale=:locale,document_revision=:rev WHERE order_id=:id"),{"number":order_number,"date":order_date,"title":source_title,"locale":source_title_locale,"rev":next_revision,"id":order_id})
        ids=[append_personnel_order_lifecycle_audit(conn,order_id=order_id,action=LIFECYCLE_AUDIT_ACTION_HEADER_UPDATED,previous_status=order["status"],new_status=order["status"],previous_void_kind=None,new_void_kind=None,actor_user_id=actor_user_id,reason_code=reason_code,reason_text=reason_text,metadata_json={"before":before,"after":after,"expected_document_revision":expected_document_revision,"resulting_document_revision":next_revision,"duplicate_preview":duplicate})]
        latest=conn.execute(text("SELECT action FROM personnel_order_lifecycle_audit WHERE order_id=:id AND action IN ('DOCUMENT_CONFIRMED','DOCUMENT_REOPENED') ORDER BY created_at DESC,id DESC LIMIT 1"),{"id":order_id}).scalar()
        state="CONFIRMED" if latest=="DOCUMENT_CONFIRMED" else "NEEDS_REVIEW"
        if state=="CONFIRMED":
            ids.append(append_personnel_order_lifecycle_audit(conn,order_id=order_id,action=LIFECYCLE_AUDIT_ACTION_DOCUMENT_REOPENED,previous_status=order["status"],new_status=order["status"],previous_void_kind=None,new_void_kind=None,actor_user_id=actor_user_id,reason_code="HEADER_CHANGED",reason_text="Document header changed",metadata_json={"expected_document_revision":expected_document_revision,"resulting_document_revision":next_revision}))
            state="NEEDS_REVIEW"
    return {"header":after,"resulting_document_revision":next_revision,"document_review_state":state,"duplicate":duplicate,"audit_event_ids":[i for i in ids if i],"no_op":False}
