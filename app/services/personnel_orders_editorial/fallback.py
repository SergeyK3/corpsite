"""Legacy localized-text fallback for first editorial generate (WP-PO-EDIT-002)."""
from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection


def load_legacy_localized(conn: Connection, order_id: int) -> Dict[str, Dict[str, Optional[str]]]:
    rows = conn.execute(
        text(
            """
            SELECT locale, title, preamble
            FROM public.personnel_order_localized_texts
            WHERE order_id = :order_id
            """
        ),
        {"order_id": int(order_id)},
    ).mappings().all()
    return {
        str(r["locale"]): {
            "title": r.get("title"),
            "preamble": r.get("preamble"),
        }
        for r in rows
    }
