# tests/operational_orders/test_orm_metadata_registration.py
"""ORM metadata registration smoke tests for OO-IMP-001."""
from __future__ import annotations

import importlib

import pytest

from app.db.base import Base

OO_TABLES = (
    "operational_order_draft_workspaces",
    "operational_order_draft_blocks",
    "operational_order_text_provenance",
    "operational_order_clarifications",
    "operational_order_draft_audit",
)


def test_operational_orders_models_registered_via_model_registry() -> None:
    import app.db.models  # noqa: F401

    for table_name in OO_TABLES:
        assert table_name in Base.metadata.tables, table_name


def test_models_registered_without_operational_orders_router_import() -> None:
    import sys

    router_modules = [name for name in sys.modules if name.startswith("app.operational_orders.router")]
    for name in router_modules:
        sys.modules.pop(name, None)

    importlib.reload(importlib.import_module("app.db.models"))

    for table_name in OO_TABLES:
        assert table_name in Base.metadata.tables, table_name


def test_model_classes_map_to_expected_tables() -> None:
    from app.db.models.operational_orders import (
        OperationalOrderClarification,
        OperationalOrderDraftAudit,
        OperationalOrderDraftBlock,
        OperationalOrderDraftWorkspace,
        OperationalOrderTextProvenance,
    )

    assert OperationalOrderDraftWorkspace.__tablename__ == "operational_order_draft_workspaces"
    assert OperationalOrderDraftBlock.__tablename__ == "operational_order_draft_blocks"
    assert OperationalOrderTextProvenance.__tablename__ == "operational_order_text_provenance"
    assert OperationalOrderClarification.__tablename__ == "operational_order_clarifications"
    assert OperationalOrderDraftAudit.__tablename__ == "operational_order_draft_audit"
