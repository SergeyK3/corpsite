"""ORM metadata registration for org_unit_allowed_positions (ADR-046 F1)."""
from __future__ import annotations

import importlib

from app.db.base import Base


def test_org_unit_allowed_position_registered_via_model_registry() -> None:
    import app.db.models  # noqa: F401

    assert "org_unit_allowed_positions" in Base.metadata.tables


def test_org_unit_allowed_position_registered_without_router_import() -> None:
    import sys

    router_modules = [name for name in sys.modules if name.startswith("app.directory.positions_routes")]
    for name in router_modules:
        sys.modules.pop(name, None)

    importlib.reload(importlib.import_module("app.db.models"))

    assert "org_unit_allowed_positions" in Base.metadata.tables


def test_model_class_maps_to_expected_table() -> None:
    from app.db.models.org_unit_allowed_positions import OrgUnitAllowedPosition

    assert OrgUnitAllowedPosition.__tablename__ == "org_unit_allowed_positions"
