"""Fail-closed preview and atomic soft-delete for one isolated DRAFT order."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.db.engine import engine

ORDER_CHILD_ALLOWLIST = frozenset({
    "personnel_order_items",
    "personnel_order_attachments", "personnel_order_editorial_blocks",
    "personnel_order_localized_texts", "personnel_order_prints",
    "personnel_order_evidence_scopes",
})
ITEM_CHILD_ALLOWLIST = frozenset({"personnel_order_item_editorial_blocks", "personnel_order_item_bases"})
BLOCKING_TABLES = frozenset({
    "employee_events",
    "personnel_order_lifecycle_audit", "personnel_order_acknowledgement_events",
})


class DraftDeletionError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code, self.message, self.status_code = code, message, status_code
        super().__init__(message)


def _fk_rows(conn, referenced_table: str, ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    rows = conn.execute(text("""SELECT c.conrelid::regclass::text AS table_name, a.attname AS column_name, c.conname
      FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=ANY(c.conkey)
      WHERE c.contype='f' AND c.confrelid=to_regclass(:referenced)"""), {"referenced": f"public.{referenced_table}"}).mappings()
    result = []
    for row in rows:
        table = str(row["table_name"]).split(".")[-1]
        count = int(conn.execute(text(f"SELECT count(*) FROM public.{table} WHERE {row['column_name']} = ANY(:ids)"), {"ids": ids}).scalar_one())
        if count:
            result.append({"table": table, "column": row["column_name"], "constraint": row["conname"], "count": count})
    return result


def _ensure_scope(conn, order_id: int, scope_unit_ids: list[int] | None) -> None:
    """Fail closed for a limited HR scope; organization-wide scope is ``None``."""
    if scope_unit_ids is None:
        return
    permitted = conn.execute(text("""
        SELECT NOT EXISTS (
          SELECT 1
          FROM public.personnel_order_items poi
          LEFT JOIN public.employees e ON e.employee_id = poi.employee_id
          WHERE poi.order_id = :order_id
            AND (e.org_unit_id IS NULL OR e.org_unit_id <> ALL(:scope_unit_ids))
        ) AND EXISTS (
          SELECT 1 FROM public.personnel_order_items WHERE order_id = :order_id
        )
    """), {"order_id": order_id, "scope_unit_ids": scope_unit_ids}).scalar_one()
    if not permitted:
        raise DraftDeletionError("DRAFT_ORDER_SCOPE_FORBIDDEN", "Personnel order is outside your organizational scope.", 403)


def _preview_tx(conn, order_id: int, *, lock: bool = False, scope_unit_ids: list[int] | None = None) -> dict[str, Any]:
    suffix = " FOR UPDATE" if lock else ""
    order = conn.execute(text(f"SELECT * FROM public.personnel_orders WHERE order_id=:id{suffix}"), {"id": order_id}).mappings().first()
    if not order:
        raise DraftDeletionError("DRAFT_ORDER_NOT_FOUND", "Personnel order not found.", 404)
    order = dict(order)
    if order.get("deleted_at") is not None:
        raise DraftDeletionError("DRAFT_ORDER_ALREADY_DELETED", "Personnel order has already been removed from the working contour.")
    if str(order.get("status")) != "DRAFT":
        raise DraftDeletionError("DRAFT_ORDER_STATUS_REQUIRED", "Only DRAFT personnel orders may be deleted.")
    _ensure_scope(conn, order_id, scope_unit_ids)
    item_ids = [int(v) for v in conn.execute(text("SELECT item_id FROM public.personnel_order_items WHERE order_id=:id"), {"id": order_id}).scalars()]
    refs = _fk_rows(conn, "personnel_orders", [order_id]) + _fk_rows(conn, "personnel_order_items", item_ids)
    # Applications are retained immutable audit, not an unknown FK blocker.
    allowed = ORDER_CHILD_ALLOWLIST | ITEM_CHILD_ALLOWLIST | {"personnel_order_template_applications"}
    blockers = [ref for ref in refs if ref["table"] in BLOCKING_TABLES or ref["table"] not in allowed]
    retained_refs = [ref for ref in refs if ref["table"] == "personnel_order_template_applications"]
    return {"order": {key: order.get(key) for key in ("order_id", "order_number", "order_date", "order_type_code", "status", "storage_json")}, "planned_deletions": [{"table": "personnel_orders", "column": "order_id", "count": 1}], "retained": ["employees", "employee_events", "template applications", "lifecycle and acknowledgement audit"], "retained_dependencies": retained_refs, "blocking_dependencies": blockers, "can_delete": not blockers, "confirmation_phrase": f"DELETE DRAFT ORDER {order_id}", "deletion_mode": "SOFT_DELETE"}


def preview(order_id: int, *, scope_unit_ids: list[int] | None = None) -> dict[str, Any]:
    with engine.connect() as conn:
        return _preview_tx(conn, int(order_id), scope_unit_ids=scope_unit_ids)


def execute(*, order_id: int, actor_user_id: int, reason: str, confirmation_phrase: str, scope_unit_ids: list[int] | None = None) -> dict[str, Any]:
    if not reason or not reason.strip():
        raise DraftDeletionError("DRAFT_ORDER_REASON_REQUIRED", "Reason is required.", 422)
    if confirmation_phrase != f"DELETE DRAFT ORDER {int(order_id)}":
        raise DraftDeletionError("DRAFT_ORDER_CONFIRMATION_REQUIRED", "Confirmation must contain the exact order_id.", 422)
    with engine.begin() as conn:
        plan = _preview_tx(conn, int(order_id), lock=True, scope_unit_ids=scope_unit_ids)
        if plan["blocking_dependencies"]:
            raise DraftDeletionError("DRAFT_ORDER_DEPENDENCY_BLOCKED", "Blocking or unknown dependencies exist.")
        snapshot = dict(plan["order"])
        snapshot["items"] = [dict(row) for row in conn.execute(text("SELECT * FROM public.personnel_order_items WHERE order_id=:id ORDER BY item_number,item_id"), {"id": order_id}).mappings()]
        snapshot["template_applications"] = [dict(row) for row in conn.execute(text("SELECT * FROM public.personnel_order_template_applications WHERE order_id=:id"), {"id": order_id}).mappings()]
        deleted = conn.execute(text("UPDATE public.personnel_orders SET deleted_at=now(), deleted_by_user_id=:actor, deletion_reason=:reason, updated_at=now() WHERE order_id=:id AND status='DRAFT' AND deleted_at IS NULL"), {"id": order_id, "actor": actor_user_id, "reason": reason.strip()})
        if deleted.rowcount != 1:
            raise DraftDeletionError("DRAFT_ORDER_CHANGED", "Personnel order changed during deletion.")
        conn.execute(text("""INSERT INTO public.personnel_order_draft_deletion_audit
          (order_id, order_snapshot, deleted_dependencies, actor_user_id, reason_text, result_code, deletion_mode)
          VALUES (:id, CAST(:snapshot AS jsonb), CAST(:dependencies AS jsonb), :actor, :reason, 'COMPLETED', 'SOFT_DELETE')"""),
          {"id": order_id, "snapshot": json.dumps(snapshot, default=str), "dependencies": json.dumps(plan["planned_deletions"]), "actor": actor_user_id, "reason": reason.strip()})
    return {"status": "SOFT_DELETED", "order_id": int(order_id)}


def execute_hr_head(*, order_id: int, actor_user_id: int) -> dict[str, Any]:
    """Soft-delete any active order under the explicitly privileged HR_HEAD rule.

    This does not undo operational effects or erase related rows.  It only removes
    the order from the working contour and records the retained snapshot in the
    existing append-only deletion audit.
    """
    with engine.begin() as conn:
        order = conn.execute(
            text("SELECT * FROM public.personnel_orders WHERE order_id=:id FOR UPDATE"),
            {"id": int(order_id)},
        ).mappings().first()
        if not order:
            raise DraftDeletionError("DRAFT_ORDER_NOT_FOUND", "Personnel order not found.", 404)
        order = dict(order)
        if order.get("deleted_at") is not None:
            raise DraftDeletionError(
                "DRAFT_ORDER_ALREADY_DELETED",
                "Personnel order has already been removed from the working contour.",
            )

        snapshot = dict(order)
        snapshot["items"] = [dict(row) for row in conn.execute(
            text("SELECT * FROM public.personnel_order_items WHERE order_id=:id ORDER BY item_number,item_id"),
            {"id": int(order_id)},
        ).mappings()]
        snapshot["template_applications"] = [dict(row) for row in conn.execute(
            text("SELECT * FROM public.personnel_order_template_applications WHERE order_id=:id"),
            {"id": int(order_id)},
        ).mappings()]

        deleted = conn.execute(text("""
            UPDATE public.personnel_orders
            SET deleted_at=now(), deleted_by_user_id=:actor,
                deletion_reason=:reason, updated_at=now()
            WHERE order_id=:id AND deleted_at IS NULL
        """), {
            "id": int(order_id),
            "actor": actor_user_id,
            "reason": "HR_HEAD order deletion",
        })
        if deleted.rowcount != 1:
            raise DraftDeletionError("DRAFT_ORDER_CHANGED", "Personnel order changed during deletion.")
        conn.execute(text("""
            INSERT INTO public.personnel_order_draft_deletion_audit
              (order_id, order_snapshot, deleted_dependencies, actor_user_id, reason_text, result_code, deletion_mode)
            VALUES (:id, CAST(:snapshot AS jsonb), CAST(:dependencies AS jsonb), :actor, :reason, 'COMPLETED', 'SOFT_DELETE')
        """), {
            "id": int(order_id),
            "snapshot": json.dumps(snapshot, default=str),
            "dependencies": json.dumps([{"table": "personnel_orders", "column": "order_id", "count": 1}]),
            "actor": actor_user_id,
            "reason": "HR_HEAD order deletion",
        })
    return {"status": "SOFT_DELETED", "order_id": int(order_id)}


def execute_physical_delete(*, order_id: int) -> dict[str, Any]:
    """Permanently remove one order and every currently known order-owned row.

    The caller has already passed the ADMIN/HR_HEAD route guard.  The flag is
    transaction-local and only relaxes the four append-only guards needed to
    remove rows which otherwise make the parent FK-restricted.
    """
    with engine.begin() as conn:
        order = conn.execute(text("SELECT order_id FROM public.personnel_orders WHERE order_id=:id FOR UPDATE"), {"id": int(order_id)}).first()
        if not order:
            raise DraftDeletionError("PERSONNEL_ORDER_NOT_FOUND", "Personnel order not found.", 404)
        conn.execute(text("SELECT set_config('corpsite.allow_personnel_order_physical_delete', 'on', true)"))
        item_ids = [int(row) for row in conn.execute(text("SELECT item_id FROM public.personnel_order_items WHERE order_id=:id FOR UPDATE"), {"id": int(order_id)}).scalars()]
        if item_ids:
            conn.execute(text("DELETE FROM public.employee_events WHERE order_id=:id OR order_item_id = ANY(:item_ids)"), {"id": int(order_id), "item_ids": item_ids})
            conn.execute(text("DELETE FROM public.personnel_order_template_applications WHERE order_id=:id OR order_item_id = ANY(:item_ids)"), {"id": int(order_id), "item_ids": item_ids})
            conn.execute(text("DELETE FROM public.personnel_order_item_bases WHERE order_item_id = ANY(:item_ids)"), {"item_ids": item_ids})
            conn.execute(text("DELETE FROM public.personnel_order_item_editorial_blocks WHERE order_item_id = ANY(:item_ids)"), {"item_ids": item_ids})
        else:
            conn.execute(text("DELETE FROM public.employee_events WHERE order_id=:id"), {"id": int(order_id)})
            conn.execute(text("DELETE FROM public.personnel_order_template_applications WHERE order_id=:id"), {"id": int(order_id)})
        for table, column in (
            ("incoming_document_personnel_order_links", "personnel_order_id"),
            ("personnel_applications", "personnel_order_id"),
            ("personnel_order_acknowledgement_events", "order_id"),
            ("personnel_order_attachments", "order_id"),
            ("personnel_order_editorial_blocks", "order_id"),
            ("personnel_order_evidence_scopes", "order_id"),
            ("personnel_order_lifecycle_audit", "order_id"),
            ("personnel_order_localized_texts", "order_id"),
            ("personnel_order_prints", "order_id"),
            ("personnel_order_draft_deletion_audit", "order_id"),
            ("technical_personnel_order_deletion_audit", "order_id"),
            ("technical_personnel_order_provenance_audit", "order_id"),
        ):
            conn.execute(text(f"DELETE FROM public.{table} WHERE {column}=:id"), {"id": int(order_id)})
        conn.execute(text("DELETE FROM public.personnel_order_items WHERE order_id=:id"), {"id": int(order_id)})
        deleted = conn.execute(text("DELETE FROM public.personnel_orders WHERE order_id=:id"), {"id": int(order_id)})
        if deleted.rowcount != 1:
            raise DraftDeletionError("PERSONNEL_ORDER_CHANGED", "Personnel order changed during deletion.")
    return {"status": "PHYSICALLY_DELETED", "order_id": int(order_id)}
