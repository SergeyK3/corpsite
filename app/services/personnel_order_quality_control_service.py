"""Read-only, live quality-control projection for personnel orders."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

from app.db.engine import engine


QUALITY_REASONS = frozenset({"CONFIRMED_TECHNICAL", "LEGACY_TECHNICAL_CANDIDATE", "MISSING_DISPLAY_TITLE", "DAMAGED_DISPLAY_TITLE"})


def list_personnel_order_quality_issues(*, limit: int = 25, offset: int = 0, reason: Optional[str] = None, status: Optional[str] = None, order_type_code: Optional[str] = None, q: Optional[str] = None) -> dict[str, Any]:
    """Return only strict, current-state issues; this function never writes data."""
    limit = min(max(int(limit), 1), 200)
    offset = max(int(offset), 0)
    technical = """COALESCE(po.storage_json ->> 'technical_record', 'false') = 'true'
      AND UPPER(COALESCE(po.storage_json ->> 'record_quality', '')) IN ('TECHNICAL', 'TECHNICAL_RECORD')"""
    legacy = """NOT ({technical}) AND (
      UPPER(COALESCE(po.order_number, '')) LIKE 'PERSONNEL-IMPORT-%'
      OR UPPER(COALESCE(po.order_number, '')) LIKE 'CSV-PILOT-%')""".format(technical=technical)
    missing_title = "NULLIF(BTRIM(COALESCE(po.source_title, '')), '') IS NULL"
    damaged_title = "COALESCE(po.source_title, '') LIKE '%' || chr(65533) || '%' OR COALESCE(po.source_title, '') ~ E'\\\\?{3,}'"
    reason_predicates = {"CONFIRMED_TECHNICAL": technical, "LEGACY_TECHNICAL_CANDIDATE": legacy, "MISSING_DISPLAY_TITLE": missing_title, "DAMAGED_DISPLAY_TITLE": damaged_title}
    normalized_reason = str(reason or "").strip().upper() or None
    if normalized_reason and normalized_reason not in QUALITY_REASONS:
        raise ValueError("Unknown quality-control reason.")
    filters = ["po.deleted_at IS NULL", f"(({technical}) OR ({legacy}) OR ({missing_title}) OR ({damaged_title}))"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if normalized_reason: filters.append(f"({reason_predicates[normalized_reason]})")
    if status: filters.append("po.status = :status"); params["status"] = str(status).strip().upper()
    if order_type_code: filters.append("po.order_type_code = :order_type_code"); params["order_type_code"] = str(order_type_code).strip().upper()
    if q and str(q).strip():
        filters.append("""(po.order_number ILIKE :q OR EXISTS (SELECT 1 FROM public.personnel_order_items i_q LEFT JOIN public.employees e_q ON e_q.employee_id=i_q.employee_id WHERE i_q.order_id=po.order_id AND COALESCE(NULLIF(BTRIM(i_q.payload ->> 'source_employee_name'), ''), e_q.full_name, '') ILIKE :q))""")
        params["q"] = f"%{str(q).strip()}%"
    issue_where = " AND ".join(filters)
    query = text(f"""
      SELECT po.order_id, po.order_number, po.order_date, po.status, po.order_type_code,
             po.updated_at, po.storage_json,
             ARRAY_REMOVE(ARRAY[
               CASE WHEN {technical} THEN 'CONFIRMED_TECHNICAL' END,
               CASE WHEN {legacy} THEN 'LEGACY_TECHNICAL_CANDIDATE' END,
               CASE WHEN {missing_title} THEN 'MISSING_DISPLAY_TITLE' END,
               CASE WHEN {damaged_title} THEN 'DAMAGED_DISPLAY_TITLE' END
             ], NULL) AS reasons,
             COALESCE((SELECT array_agg(DISTINCT COALESCE(NULLIF(BTRIM(i.payload ->> 'source_employee_name'), ''), e.full_name)
                       ORDER BY COALESCE(NULLIF(BTRIM(i.payload ->> 'source_employee_name'), ''), e.full_name))
                       FROM public.personnel_order_items i
                       LEFT JOIN public.employees e ON e.employee_id=i.employee_id
                       WHERE i.order_id=po.order_id), ARRAY[]::text[]) AS employee_names
      FROM public.personnel_orders po
      WHERE {issue_where}
      ORDER BY po.updated_at DESC, po.order_id DESC
      LIMIT :limit OFFSET :offset
    """)
    count = text(f"SELECT count(*) FROM public.personnel_orders po WHERE {issue_where}")
    with engine.connect() as conn:
        total = int(conn.execute(count, params).scalar_one())
        rows = conn.execute(query, params).mappings().all()
    return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}
