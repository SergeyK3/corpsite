"""ORM metadata registration for WP-ADR061-001B person photo models."""
from __future__ import annotations

import importlib

from app.db.base import Base

ADR061_001B_TABLES = (
    "person_photos",
    "person_photo_sources",
    "personnel_application_blockers",
)


def test_person_photo_models_registered_via_model_registry() -> None:
    import app.db.models  # noqa: F401

    for table_name in ADR061_001B_TABLES:
        assert table_name in Base.metadata.tables, table_name


def test_person_photo_models_registered_after_models_reload() -> None:
    importlib.reload(importlib.import_module("app.db.models"))

    for table_name in ADR061_001B_TABLES:
        assert table_name in Base.metadata.tables, table_name


def test_model_classes_map_to_expected_tables() -> None:
    from app.db.models.person_photos import (
        PersonPhoto,
        PersonPhotoSource,
        PersonnelApplicationBlocker,
    )

    assert PersonPhoto.__tablename__ == "person_photos"
    assert PersonPhotoSource.__tablename__ == "person_photo_sources"
    assert PersonnelApplicationBlocker.__tablename__ == "personnel_application_blockers"
