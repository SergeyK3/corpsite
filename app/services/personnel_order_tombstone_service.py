"""Read-only projection for an order removed from the working contour."""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_orders_query_service import PersonnelOrderNotFoundError


def get_deleted_personnel_order_tombstone(order_id: int) -> Dict[str, Any]:
    """Return the deliberately narrow admin-only tombstone projection."""
    with engine.connect() as conn:
        order = conn.execute(text("""
            SELECT po.order_id, po.order_number, po.order_type_code, po.status,
                   po.deleted_at, po.deletion_reason, po.deleted_by_user_id,
                   u.full_name AS deleted_by_name,
                   COALESCE((SELECT deletion_mode
                     FROM public.personnel_order_draft_deletion_audit a
                     WHERE a.order_id=po.order_id
                     ORDER BY a.created_at DESC, a.audit_id DESC LIMIT 1), 'SOFT_DELETE') AS deletion_mode,
                   (SELECT count(*) FROM public.personnel_order_template_applications ta
                     WHERE ta.order_id=po.order_id) AS template_application_count
            FROM public.personnel_orders po
            LEFT JOIN public.users u ON u.user_id=po.deleted_by_user_id
            WHERE po.order_id=:order_id AND po.deleted_at IS NOT NULL
        """), {"order_id": int(order_id)}).mappings().first()
        if order is None:
            raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")
        items = conn.execute(text("""
            SELECT poi.item_id, poi.item_number, poi.item_type_code, poi.item_status,
                   poi.employee_id, e.full_name AS employee_name
            FROM public.personnel_order_items poi
            LEFT JOIN public.employees e ON e.employee_id=poi.employee_id
            WHERE poi.order_id=:order_id ORDER BY poi.item_number, poi.item_id
        """), {"order_id": int(order_id)}).mappings().all()
    return {
        "order_id": int(order["order_id"]), "order_number": order["order_number"],
        "order_type_code": order["order_type_code"], "previous_status": order["status"],
        "deleted_at": order["deleted_at"].isoformat(), "deletion_reason": order["deletion_reason"],
        "deleted_by_user_id": order["deleted_by_user_id"], "deleted_by_name": order["deleted_by_name"],
        "deletion_mode": order["deletion_mode"], "template_application_count": int(order["template_application_count"]),
        "items": [dict(row) for row in items],
        "employees": list(dict.fromkeys(row["employee_name"] for row in items if row["employee_name"])),
    }
