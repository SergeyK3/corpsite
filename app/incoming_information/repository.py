"""Incoming Information schema availability helpers."""
from __future__ import annotations

from sqlalchemy import text

from app.db.engine import engine

II_TABLES = (
    "incoming_document_registration_counters",
    "incoming_document_types",
    "incoming_document_statuses",
    "incoming_planned_results",
    "incoming_receipt_channels",
    "incoming_document_link_types",
    "incoming_documents",
    "incoming_document_assignments",
    "incoming_document_attachments",
    "incoming_document_operational_order_links",
    "incoming_document_personnel_order_links",
    "incoming_document_audit",
)

DDL_REVISION = "f3a4b5c6d7e8"


def incoming_information_available() -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'incoming_documents'
                LIMIT 1
                """
            )
        ).first()
        return row is not None
