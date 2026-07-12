"""Schema availability and low-level persistence helpers."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.db.engine import engine

OO_TABLES = (
    "operational_order_draft_workspaces",
    "operational_order_draft_blocks",
    "operational_order_text_provenance",
    "operational_order_clarifications",
    "operational_order_draft_audit",
)


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table_name
            LIMIT 1
            """
        ),
        {"table_name": table},
    ).first()
    return row is not None


def operational_orders_available() -> bool:
    with engine.connect() as conn:
        return all(_table_exists(conn, table) for table in OO_TABLES)


def dumps_json(value: Any) -> str:
    return json.dumps(value if value is not None else [])


def fetch_workspace_row(conn, workspace_id: int) -> dict[str, Any] | None:
    row = (
        conn.execute(
            text(
                """
                SELECT *
                FROM public.operational_order_draft_workspaces
                WHERE workspace_id = :workspace_id
                """
            ),
            {"workspace_id": int(workspace_id)},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None
