"""Narrow, fail-closed hard-delete handler for explicitly flagged technical orders.

This is intentionally not a generic cleanup engine.  Every child table is
inspected from PostgreSQL FK metadata and only the small allowlist below may be
deleted.  New/unknown references stop the operation before any mutation.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.db.engine import engine

TECHNICAL_QUALITIES = frozenset({"TECHNICAL", "TECHNICAL_RECORD"})
CONFIRMED_TECHNICAL = "CONFIRMED_TECHNICAL"
LEGACY_TECHNICAL_CANDIDATE = "LEGACY_TECHNICAL_CANDIDATE"
REGULAR = "REGULAR"
LEGACY_PREFIXES = ("PERSONNEL-IMPORT-", "CSV-PILOT-")
ORDER_CHILD_ALLOWLIST = frozenset({
    "personnel_order_items", "personnel_order_localized_texts",
    "personnel_order_attachments", "personnel_order_prints",
    "personnel_order_editorial_blocks", "personnel_order_evidence_scopes",
})
ITEM_CHILD_ALLOWLIST = frozenset({"personnel_order_item_editorial_blocks", "personnel_order_item_bases"})
BLOCKING_TABLES = frozenset({
    "employee_events", "personnel_order_template_applications",
    "personnel_order_lifecycle_audit", "personnel_order_acknowledgement_events",
})


class TechnicalOrderCleanupError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code, self.message, self.status_code = code, message, status_code
        super().__init__(message)


def _technical_clause(alias: str = "po") -> str:
    return f"""COALESCE({alias}.storage_json ->> 'technical_record', 'false') = 'true'
        AND UPPER(COALESCE({alias}.storage_json ->> 'record_quality', ''))
            IN ('TECHNICAL', 'TECHNICAL_RECORD')"""


def _legacy_clause(alias: str = "po") -> str:
    return f"UPPER(COALESCE({alias}.order_number, '')) LIKE 'PERSONNEL-IMPORT-%' OR UPPER(COALESCE({alias}.order_number, '')) LIKE 'CSV-PILOT-%'"


def classification(storage_json: Any, order_number: Any) -> str:
    payload = storage_json if isinstance(storage_json, dict) else {}
    if payload.get("technical_record") is True and str(payload.get("record_quality") or "").upper() in TECHNICAL_QUALITIES:
        return CONFIRMED_TECHNICAL
    if str(order_number or "").strip().upper().startswith(LEGACY_PREFIXES):
        return LEGACY_TECHNICAL_CANDIDATE
    return REGULAR


def search(*, order_id: int | None = None, q: str | None = None, employee_name: str | None = None,
           import_source: str | None = None) -> list[dict[str, Any]]:
    if order_id is None and not any(str(v or "").strip() for v in (q, employee_name, import_source)):
        raise TechnicalOrderCleanupError("TECHNICAL_ORDER_SEARCH_REQUIRED", "Specify one exact identifier or search value.", 422)
    where, params = [f"({_technical_clause()} OR {_legacy_clause()})"], {}
    if order_id is not None:
        where.append("po.order_id=:order_id"); params["order_id"] = int(order_id)
    if q and q.strip():
        where.append("po.order_number ILIKE :q"); params["q"] = f"%{q.strip()}%"
    if employee_name and employee_name.strip():
        where.append("EXISTS (SELECT 1 FROM public.personnel_order_items i JOIN public.employees e ON e.employee_id=i.employee_id WHERE i.order_id=po.order_id AND COALESCE(e.full_name,'') ILIKE :employee_name)")
        params["employee_name"] = f"%{employee_name.strip()}%"
    if import_source and import_source.strip():
        where.append("po.storage_json::text ILIKE :import_source"); params["import_source"] = f"%{import_source.strip()}%"
    sql = f"""SELECT po.order_id, po.order_number, po.order_date, po.order_type_code, po.status,
        po.storage_json AS storage_json,
        po.storage_json ->> 'record_quality' AS record_quality,
        po.storage_json ->> 'import_source_id' AS import_source_id,
        COALESCE(array_agg(DISTINCT e.full_name) FILTER (WHERE e.full_name IS NOT NULL), '{{}}') AS employees
        FROM public.personnel_orders po
        LEFT JOIN public.personnel_order_items i ON i.order_id=po.order_id
        LEFT JOIN public.employees e ON e.employee_id=i.employee_id
        WHERE {' AND '.join(where)} GROUP BY po.order_id ORDER BY po.order_id DESC LIMIT 100"""
    with engine.connect() as conn:
        return [{**dict(row), "classification": classification(row.get("storage_json"), row.get("order_number"))} for row in conn.execute(text(sql), params).mappings()]


def _fk_rows(conn, referenced_table: str, ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    rows = conn.execute(text("""SELECT c.conrelid::regclass::text AS table_name,
        a.attname AS column_name, c.conname
        FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=ANY(c.conkey)
        WHERE c.contype='f' AND c.confrelid=to_regclass(:referenced)"""), {"referenced": f"public.{referenced_table}"}).mappings()
    result = []
    for row in rows:
        table = str(row["table_name"]).split(".")[-1]
        count = conn.execute(text(f"SELECT count(*) FROM public.{table} WHERE {row['column_name']} = ANY(:ids)"), {"ids": ids}).scalar_one()
        if count:
            result.append({"table": table, "column": row["column_name"], "constraint": row["conname"], "count": int(count)})
    return result


def _preview_tx(conn, order_id: int, *, lock: bool = False) -> dict[str, Any]:
    suffix = " FOR UPDATE" if lock else ""
    order = conn.execute(text(f"SELECT po.* FROM public.personnel_orders po WHERE po.order_id=:id{suffix}"), {"id": order_id}).mappings().first()
    if not order:
        raise TechnicalOrderCleanupError("TECHNICAL_ORDER_NOT_FOUND", "Order not found.", 404)
    order = dict(order)
    current_classification = classification(order.get("storage_json"), order.get("order_number"))
    technical = current_classification == CONFIRMED_TECHNICAL
    item_ids = [int(x) for x in conn.execute(text("SELECT item_id FROM public.personnel_order_items WHERE order_id=:id"), {"id": order_id}).scalars()]
    root_refs = _fk_rows(conn, "personnel_orders", [order_id])
    item_refs = _fk_rows(conn, "personnel_order_items", item_ids)
    refs = root_refs + item_refs
    blockers = [r for r in refs if r["table"] in BLOCKING_TABLES or r["table"] not in ORDER_CHILD_ALLOWLIST | ITEM_CHILD_ALLOWLIST]
    planned = [r for r in refs if r not in blockers]
    planned.append({"table": "personnel_orders", "column": "order_id", "count": 1})
    return {"order": {k: order.get(k) for k in ("order_id", "order_number", "order_date", "order_type_code", "status", "storage_json")},
            "classification": current_classification, "technical_confirmed": technical, "planned_deletions": planned,
            "retained": ["employees", "users", "template versions", "files in storage"],
            "blocking_dependencies": blockers, "can_delete": technical and not blockers,
            "confirmation_phrase": f"DELETE TECHNICAL ORDER {order_id}"}


def preview(order_id: int) -> dict[str, Any]:
    with engine.connect() as conn:
        return _preview_tx(conn, int(order_id))


def confirm_provenance_preview(order_id: int) -> dict[str, Any]:
    preview_data = preview(order_id)
    preview_data["confirmation_phrase"] = f"CONFIRM TECHNICAL ORDER {int(order_id)}"
    preview_data["can_confirm_provenance"] = preview_data["classification"] == LEGACY_TECHNICAL_CANDIDATE
    return preview_data


def confirm_provenance(*, order_id: int, actor_user_id: int, reason: str, confirmation_phrase: str) -> dict[str, Any]:
    if confirmation_phrase != f"CONFIRM TECHNICAL ORDER {int(order_id)}":
        raise TechnicalOrderCleanupError("TECHNICAL_ORDER_CONFIRMATION_REQUIRED", "Confirmation must contain the exact order_id.", 422)
    if not reason or not reason.strip():
        raise TechnicalOrderCleanupError("TECHNICAL_ORDER_REASON_REQUIRED", "Reason is required.", 422)
    with engine.begin() as conn:
        plan = _preview_tx(conn, int(order_id), lock=True)
        if plan["classification"] != LEGACY_TECHNICAL_CANDIDATE:
            raise TechnicalOrderCleanupError("TECHNICAL_ORDER_LEGACY_CANDIDATE_REQUIRED", "Only a legacy technical candidate may be confirmed.")
        prior = dict(plan["order"].get("storage_json") or {})
        import_source_id = str(prior.get("import_source_id") or prior.get("source_identifier") or f"legacy-personnel-import:{order_id}")
        canonical = {**prior, "technical_record": True, "record_quality": "TECHNICAL_RECORD", "import_source_id": import_source_id}
        conn.execute(text("UPDATE public.personnel_orders SET storage_json=CAST(:storage AS jsonb) WHERE order_id=:id"), {"id": order_id, "storage": json.dumps(canonical)})
        conn.execute(text("""INSERT INTO public.technical_personnel_order_provenance_audit
          (order_id, previous_storage_json, confirmed_storage_json, actor_user_id, reason_text, result_code)
          VALUES (:id, CAST(:previous AS jsonb), CAST(:confirmed AS jsonb), :actor, :reason, 'COMPLETED')"""),
          {"id": order_id, "previous": json.dumps(prior), "confirmed": json.dumps(canonical), "actor": actor_user_id, "reason": reason.strip()})
    return {"status": "COMPLETED", "order_id": int(order_id), "classification": CONFIRMED_TECHNICAL}


def execute(*, order_id: int, actor_user_id: int, reason: str, confirmation_phrase: str) -> dict[str, Any]:
    if confirmation_phrase != f"DELETE TECHNICAL ORDER {int(order_id)}":
        raise TechnicalOrderCleanupError("TECHNICAL_ORDER_CONFIRMATION_REQUIRED", "Confirmation must contain the exact order_id.", 422)
    if not reason or not reason.strip():
        raise TechnicalOrderCleanupError("TECHNICAL_ORDER_REASON_REQUIRED", "Reason is required.", 422)
    with engine.begin() as conn:
        plan = _preview_tx(conn, int(order_id), lock=True)
        if not plan["technical_confirmed"]:
            raise TechnicalOrderCleanupError("TECHNICAL_ORDER_FLAG_REQUIRED", "The order lacks the confirmed technical-record marker.")
        if plan["blocking_dependencies"]:
            raise TechnicalOrderCleanupError("TECHNICAL_ORDER_DEPENDENCY_BLOCKED", "Blocking or unknown FK dependencies exist.")
        item_ids = [int(x) for x in conn.execute(text("SELECT item_id FROM public.personnel_order_items WHERE order_id=:id"), {"id": order_id}).scalars()]
        for table in ITEM_CHILD_ALLOWLIST:
            conn.execute(text(f"DELETE FROM public.{table} WHERE order_item_id = ANY(:ids)"), {"ids": item_ids})
        for table in ORDER_CHILD_ALLOWLIST - {"personnel_order_items"}:
            conn.execute(text(f"DELETE FROM public.{table} WHERE order_id=:id"), {"id": order_id})
        conn.execute(text("DELETE FROM public.personnel_order_items WHERE order_id=:id"), {"id": order_id})
        conn.execute(text("DELETE FROM public.personnel_orders WHERE order_id=:id"), {"id": order_id})
        conn.execute(text("""INSERT INTO public.technical_personnel_order_deletion_audit
            (order_id, order_snapshot, deleted_dependencies, actor_user_id, reason_text, result_code)
            VALUES (:id, CAST(:snapshot AS jsonb), CAST(:dependencies AS jsonb), :actor, :reason, 'COMPLETED')"""),
            {"id": order_id, "snapshot": json.dumps(plan["order"], default=str), "dependencies": json.dumps(plan["planned_deletions"]), "actor": actor_user_id, "reason": reason.strip()})
    return {"status": "COMPLETED", "order_id": int(order_id), "deleted": plan["planned_deletions"]}
