# FILE: app/services/professional_documents_service.py
"""ADR-034 local demonstration read-model (not production)."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.db.engine import engine


def _table_exists(conn, table: str, schema: str = "public") -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema AND table_name = :table
            LIMIT 1
            """
        ),
        {"schema": schema, "table": table},
    ).first()
    return row is not None


def professional_documents_available() -> bool:
    """True when local ADR-034 demo tables are present."""
    with engine.begin() as conn:
        return _table_exists(conn, "certificate_types") and _table_exists(
            conn, "employee_certificates"
        )


def _empty_response() -> Dict[str, Any]:
    return {"items": [], "total": 0, "available": False}


def _compute_status(expires_at: Optional[date], *, today: date) -> str:
    if expires_at is None:
        return "VALID"
    days_left = (expires_at - today).days
    if days_left < 0:
        return "EXPIRED"
    if days_left <= 30:
        return "EXPIRING_30"
    if days_left <= 60:
        return "EXPIRING_60"
    return "VALID"


def list_professional_documents_demo() -> Dict[str, Any]:
    """Return certificate rows plus synthetic MISSING rows for local demo."""
    if not professional_documents_available():
        return _empty_response()

    today = date.today()

    q_certs = text(
        """
        SELECT
            ec.certificate_id,
            ec.employee_id,
            e.full_name AS employee_name,
            ct.certificate_type_id,
            ct.code AS certificate_type_code,
            ct.name AS certificate_type_name,
            ec.expires_at
        FROM public.employee_certificates ec
        JOIN public.employees e ON e.employee_id = ec.employee_id
        JOIN public.certificate_types ct ON ct.certificate_type_id = ec.certificate_type_id
        WHERE ec.is_current = TRUE
        ORDER BY e.full_name, ct.name
        """
    )

    q_missing = text(
        """
        SELECT
            e.employee_id,
            e.full_name AS employee_name,
            ct.certificate_type_id,
            ct.code AS certificate_type_code,
            ct.name AS certificate_type_name
        FROM public.employees e
        CROSS JOIN public.certificate_types ct
        LEFT JOIN public.employee_certificates ec
          ON ec.employee_id = e.employee_id
         AND ec.certificate_type_id = ct.certificate_type_id
         AND ec.is_current = TRUE
        WHERE e.is_active = TRUE
          AND ct.is_active = TRUE
          AND ct.code = 'MED_SPEC'
          AND ec.certificate_id IS NULL
        ORDER BY e.full_name
        LIMIT 5
        """
    )

    items: List[Dict[str, Any]] = []

    with engine.begin() as conn:
        cert_rows = conn.execute(q_certs).mappings().all()
        missing_rows = conn.execute(q_missing).mappings().all()

    for r in cert_rows:
        exp = r.get("expires_at")
        expires_iso = exp.isoformat() if hasattr(exp, "isoformat") else exp
        status = _compute_status(exp if isinstance(exp, date) else None, today=today)
        items.append(
            {
                "certificate_id": int(r["certificate_id"]),
                "employee_id": int(r["employee_id"]),
                "employee_name": str(r.get("employee_name") or ""),
                "certificate_type_name": str(r.get("certificate_type_name") or ""),
                "expires_at": expires_iso,
                "status": status,
            }
        )

    for r in missing_rows:
        items.append(
            {
                "certificate_id": None,
                "employee_id": int(r["employee_id"]),
                "employee_name": str(r.get("employee_name") or ""),
                "certificate_type_name": str(r.get("certificate_type_name") or ""),
                "expires_at": None,
                "status": "MISSING",
            }
        )

    status_order = {
        "EXPIRED": 0,
        "EXPIRING_30": 1,
        "EXPIRING_60": 2,
        "VALID": 3,
        "MISSING": 4,
    }
    items.sort(key=lambda x: (status_order.get(x["status"], 9), x.get("employee_name") or ""))

    return {"items": items, "total": len(items), "available": True}
