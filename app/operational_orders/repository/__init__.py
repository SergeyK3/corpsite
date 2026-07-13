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
    "operational_order_translation_assignments",
    "operational_order_content_confirmations",
    "operational_order_bilingual_reconciliations",
)

OO_DOCUMENT_TABLES = (
    "operational_order_promotions",
    "operational_order_documents",
    "operational_order_document_versions",
    "operational_order_document_localizations",
    "operational_order_promotion_audit",
)

OO_LIFECYCLE_TABLES = (
    "operational_order_signing_authority",
    "operational_order_lifecycle_audit",
)

OO_SIGNING_COMMAND_TABLES = (
    "operational_order_signing_attestations",
    "operational_order_lifecycle_command_idempotency",
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


def document_aggregate_available() -> bool:
    with engine.connect() as conn:
        return operational_orders_available() and all(
            _table_exists(conn, table) for table in OO_DOCUMENT_TABLES
        )


def lifecycle_available() -> bool:
    with engine.connect() as conn:
        return document_aggregate_available() and all(
            _table_exists(conn, table) for table in OO_LIFECYCLE_TABLES
        )


def signing_command_available() -> bool:
    with engine.connect() as conn:
        return lifecycle_available() and all(
            _table_exists(conn, table) for table in OO_SIGNING_COMMAND_TABLES
        )


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
