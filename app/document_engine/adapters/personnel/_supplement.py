"""Read-only supplement loader for API gaps (UDE-008)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import text

from app.db.engine import engine


def fetch_order_supplement(order_id: int) -> Dict[str, Any]:
    """Load DB-only fields missing from PersonnelOrderHeaderOut."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    void_kind,
                    archived_at,
                    archived_by,
                    archive_reason_code,
                    archive_reason_text
                FROM public.personnel_orders
                WHERE order_id = :order_id
                """
            ),
            {"order_id": int(order_id)},
        ).mappings().first()
    if not row:
        return {}
    return {
        "void_kind": row.get("void_kind"),
        "archived_at": row.get("archived_at"),
        "archived_by": int(row["archived_by"]) if row.get("archived_by") is not None else None,
        "archive_reason_code": row.get("archive_reason_code"),
        "archive_reason_text": row.get("archive_reason_text"),
    }


def void_kind_for_header(
    header: Dict[str, Any],
    supplement: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    if supplement and supplement.get("void_kind"):
        return str(supplement["void_kind"])
    if header.get("void_kind"):
        return str(header["void_kind"])
    return None
