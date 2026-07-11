"""Editorial schema availability checks (WP-PO-EDIT-002)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.personnel_orders_query_service import (
    PersonnelOrderValidationError,
    personnel_orders_available,
)

EDITORIAL_TABLES = (
    "personnel_order_editorial_blocks",
    "personnel_order_item_editorial_blocks",
    "personnel_order_item_bases",
)


def editorial_tables_available(conn: Optional[Connection] = None) -> bool:
    def _check(c: Connection) -> bool:
        for table_name in EDITORIAL_TABLES:
            row = c.execute(
                text(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = :table_name
                    LIMIT 1
                    """
                ),
                {"table_name": table_name},
            ).first()
            if row is None:
                return False
        return True

    if conn is not None:
        return _check(conn)
    with engine.begin() as owned:
        return _check(owned)


def require_available() -> None:
    if not personnel_orders_available():
        raise PersonnelOrderValidationError("Personnel orders schema is not available.")
    if not editorial_tables_available():
        raise PersonnelOrderValidationError("Personnel order editorial schema is not available.")
