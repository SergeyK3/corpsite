"""Document-only personnel order review; never changes lifecycle or HR facts."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_orders import (
    LIFECYCLE_AUDIT_ACTION_DOCUMENT_CONFIRMED,
    LIFECYCLE_AUDIT_ACTION_DOCUMENT_REOPENED,
)
from app.services.personnel_order_lifecycle_audit_service import append_personnel_order_lifecycle_audit
from app.services.personnel_orders_query_service import PersonnelOrderNotFoundError


class PersonnelOrderDocumentReviewConflictError(Exception):
    pass


class PersonnelOrderDocumentReviewValidationError(Exception):
    def __init__(self, blockers: List[Dict[str, Any]]):
        self.blockers = blockers
        super().__init__("DOCUMENT_REVIEW_BLOCKED")


def _review(conn, order_id: int, *, lock: bool = False) -> Dict[str, Any]:
    order = conn.execute(text(f"SELECT order_id, order_number, order_date, status, document_revision, storage_json FROM public.personnel_orders WHERE order_id=:id {'FOR UPDATE' if lock else ''}"), {"id": order_id}).mappings().one_or_none()
    if order is None:
        raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")
    latest = conn.execute(text("""SELECT action, actor_user_id, reason_code, reason_text, created_at, metadata_json
        FROM public.personnel_order_lifecycle_audit WHERE order_id=:id
        AND action IN ('DOCUMENT_CONFIRMED','DOCUMENT_REOPENED') ORDER BY created_at DESC, id DESC LIMIT 1"""), {"id": order_id}).mappings().one_or_none()
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    if not str(order["order_number"] or "").strip(): blockers.append({"code": "MISSING_ORDER_NUMBER"})
    if order["order_date"] is None: blockers.append({"code": "MISSING_ORDER_DATE"})
    items = conn.execute(text("""SELECT item_id, item_type_code, employee_id, payload FROM public.personnel_order_items
        WHERE order_id=:id AND item_status='ACTIVE' ORDER BY item_number"""), {"id": order_id}).mappings().all()
    if not items: blockers.append({"code": "MISSING_ACTIVE_ITEMS"})
    for item in items:
        if not str(item["item_type_code"] or "").strip(): blockers.append({"code": "MISSING_ITEM_TYPE", "item_id": int(item["item_id"])})
        payload = item["payload"] or {}
        if item["employee_id"] is None and not str(payload.get("unresolved_subject") or payload.get("source_full_name") or "").strip():
            blockers.append({"code": "MISSING_SUBJECT", "item_id": int(item["item_id"])})
    block_rows = conn.execute(text("""SELECT locale, review_status FROM public.personnel_order_editorial_blocks WHERE order_id=:id
        UNION ALL SELECT locale, review_status FROM public.personnel_order_item_editorial_blocks ib
        JOIN public.personnel_order_items i ON i.item_id=ib.order_item_id WHERE i.order_id=:id AND i.item_status='ACTIVE'"""), {"id": order_id}).mappings().all()
    locales = {str(row["locale"]) for row in block_rows}
    for locale in ("ru", "kk"):
        if locale not in locales: blockers.append({"code": "MISSING_DOCUMENT_PRESENTATION", "locale": locale})
    for row in block_rows:
        status = str(row["review_status"] or "")
        if status == "GENERATION_FAILED": blockers.append({"code": "EDITORIAL_GENERATION_FAILED", "locale": row["locale"]})
        elif status in {"STALE", "REVIEW_REQUIRED"}: warnings.append({"code": "EDITORIAL_REVIEW_REQUIRED", "locale": row["locale"]})
    if (order["storage_json"] or {}).get("reconstruction_status") == "NEEDS_DOCX_REVIEW": warnings.append({"code": "NEEDS_DOCX_REVIEW"})
    state = "CONFIRMED" if latest and latest["action"] == LIFECYCLE_AUDIT_ACTION_DOCUMENT_CONFIRMED else "NEEDS_REVIEW"
    return {"state": state, "document_revision": int(order["document_revision"]), "confirmed_at": latest["created_at"].isoformat() if latest and latest["action"] == LIFECYCLE_AUDIT_ACTION_DOCUMENT_CONFIRMED else None, "confirmed_by": int(latest["actor_user_id"]) if latest and latest["action"] == LIFECYCLE_AUDIT_ACTION_DOCUMENT_CONFIRMED else None, "latest_reason_code": latest["reason_code"] if latest else None, "latest_note": latest["reason_text"] if latest else None, "blockers": blockers, "warnings": warnings, "allowed_actions": (["reopen"] if state == "CONFIRMED" else (["confirm"] if not blockers else [])), "order": order}


def get_document_review(order_id: int) -> Dict[str, Any]:
    with engine.begin() as conn:
        result = _review(conn, int(order_id))
    result.pop("order", None)
    return result


def mutate_document_review(order_id: int, *, action: str, expected_document_revision: int, reason_code: str, note: Optional[str], actor_user_id: int) -> Dict[str, Any]:
    action = str(action).upper()
    with engine.begin() as conn:
        current = _review(conn, int(order_id), lock=True)
        if current["document_revision"] != int(expected_document_revision):
            raise PersonnelOrderDocumentReviewConflictError("DOCUMENT_REVISION_CONFLICT")
        desired = "CONFIRMED" if action == LIFECYCLE_AUDIT_ACTION_DOCUMENT_CONFIRMED else "NEEDS_REVIEW"
        if action == LIFECYCLE_AUDIT_ACTION_DOCUMENT_REOPENED and not str(note or "").strip():
            raise PersonnelOrderDocumentReviewValidationError([{"code": "REOPEN_NOTE_REQUIRED"}])
        if current["state"] == desired:
            current.pop("order", None)
            return current
        if action == LIFECYCLE_AUDIT_ACTION_DOCUMENT_CONFIRMED and current["blockers"]:
            raise PersonnelOrderDocumentReviewValidationError(current["blockers"])
        next_revision = current["document_revision"] + 1
        order = current["order"]
        conn.execute(text("UPDATE public.personnel_orders SET document_revision=:revision WHERE order_id=:id"), {"revision": next_revision, "id": int(order_id)})
        append_personnel_order_lifecycle_audit(conn, order_id=int(order_id), action=action,
            previous_status=str(order["status"]), new_status=str(order["status"]), previous_void_kind=None, new_void_kind=None,
            actor_user_id=int(actor_user_id), reason_code=str(reason_code).strip(), reason_text=str(note).strip() or None,
            metadata_json={"previous_document_state": current["state"], "new_document_state": desired,
                "expected_document_revision": int(expected_document_revision), "resulting_document_revision": next_revision,
                "validation": {"blockers": current["blockers"], "warnings": current["warnings"]}})
        result = _review(conn, int(order_id))
    result.pop("order", None)
    return result
