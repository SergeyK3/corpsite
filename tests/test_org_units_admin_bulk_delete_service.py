# tests/test_org_units_admin_bulk_delete_service.py
"""Unit tests for bulk org unit delete service contract."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.org_units_admin_service import (
    bulk_delete_admin_org_units,
    preview_bulk_delete_admin_org_units,
)


class _FakeUnit:
    def __init__(self, *, unit_id: int, name: str, parent_unit_id: int | None = 10) -> None:
        self.unit_id = unit_id
        self.parent_unit_id = parent_unit_id
        self.name = name
        self.code = None
        self.group_id = 1
        self.is_active = True


def _subtree_rows(root_id: int, children: list[dict] | None = None) -> list[dict]:
    rows = [
        {
            "unit_id": root_id,
            "parent_unit_id": 10,
            "name": f"Root {root_id}",
            "depth": 0,
        }
    ]
    for child in children or []:
        rows.append(
            {
                "unit_id": int(child["unit_id"]),
                "parent_unit_id": int(child.get("parent_unit_id", root_id)),
                "name": child.get("name", f"Child {child['unit_id']}"),
                "depth": int(child.get("depth", 1)),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["depth"]), int(row["unit_id"])))


@pytest.fixture
def mock_engine():
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    delete_result = MagicMock()
    delete_result.rowcount = 1
    conn.execute.return_value = delete_result

    engine = MagicMock()
    engine.connect.return_value = conn
    engine.begin.return_value = conn
    return engine, conn


@patch("app.services.org_units_admin_service._audit_org_unit_event")
@patch("app.services.org_units_admin_service._fetch_subtree_units")
@patch("app.services.org_units_admin_service._normalize_bulk_delete_roots")
@patch("app.services.org_units_admin_service._blocking_dependencies_for_subtree_unit")
@patch("app.services.org_units_admin_service._ORG_UNITS")
def test_bulk_delete_removes_subtree_bottom_up(
    mock_org_units,
    mock_blocking,
    mock_normalize,
    mock_fetch_subtree,
    _mock_audit,
    mock_engine,
):
    engine, conn = mock_engine
    mock_normalize.return_value = ([1], [])
    mock_org_units.get_org_unit.return_value = _FakeUnit(unit_id=1, name="Отдел A", parent_unit_id=10)
    mock_fetch_subtree.return_value = _subtree_rows(1, [{"unit_id": 2, "name": "Дочерний"}])
    mock_blocking.return_value = {}

    result = bulk_delete_admin_org_units(actor_user_id=99, unit_ids=[1], db_engine=engine)

    assert result["deleted_ids"] == [2, 1]
    assert result["failed"] == []
    assert conn.execute.call_count == 2


@patch("app.services.org_units_admin_service._audit_org_unit_event")
@patch("app.services.org_units_admin_service._fetch_subtree_units")
@patch("app.services.org_units_admin_service._normalize_bulk_delete_roots")
@patch("app.services.org_units_admin_service._blocking_dependencies_for_subtree_unit")
@patch("app.services.org_units_admin_service._ORG_UNITS")
def test_bulk_delete_blocks_subtree_when_child_has_external_dependency(
    mock_org_units,
    mock_blocking,
    mock_normalize,
    mock_fetch_subtree,
    _mock_audit,
    mock_engine,
):
    engine, _conn = mock_engine
    mock_normalize.return_value = ([1], [])
    mock_org_units.get_org_unit.return_value = _FakeUnit(unit_id=1, name="Отдел A", parent_unit_id=10)
    mock_fetch_subtree.return_value = _subtree_rows(
        1,
        [{"unit_id": 2, "name": "Дочерний с зависимостью"}],
    )

    def _blocking_side_effect(unit_id: int, **_kwargs):
        if unit_id == 2:
            return {"users": 1}
        return {}

    mock_blocking.side_effect = _blocking_side_effect

    result = bulk_delete_admin_org_units(actor_user_id=99, unit_ids=[1], db_engine=engine)

    assert result["deleted_ids"] == []
    assert len(result["failed"]) == 1
    assert result["failed"][0]["reason_code"] == "SUBTREE_HAS_DEPENDENCIES"
    assert result["failed"][0]["blocked_units"] == [
        {
            "id": 2,
            "name": "Дочерний с зависимостью",
            "dependencies": {"users": 1},
        }
    ]
    engine.begin.assert_not_called()


@patch("app.services.org_units_admin_service._fetch_subtree_units")
@patch("app.services.org_units_admin_service._normalize_bulk_delete_roots")
@patch("app.services.org_units_admin_service._ORG_UNITS")
def test_preview_bulk_delete_skips_covered_child_selection(
    mock_org_units,
    mock_normalize,
    mock_fetch_subtree,
    mock_engine,
):
    engine, conn = mock_engine
    mock_normalize.return_value = ([1], [(2, 1)])
    mock_org_units.get_org_unit.return_value = _FakeUnit(unit_id=1, name="Отдел A", parent_unit_id=10)
    mock_fetch_subtree.return_value = _subtree_rows(1, [{"unit_id": 2, "name": "Дочерний"}])

    preview = preview_bulk_delete_admin_org_units(unit_ids=[1, 2], db_engine=engine)

    assert preview["requested"] == 2
    assert preview["roots"] == [
        {
            "id": 1,
            "name": "Отдел A",
            "descendants": [{"id": 2, "name": "Дочерний"}],
            "subtree_size": 2,
        }
    ]
    assert preview["skipped_as_covered"] == [{"id": 2, "covered_by": 1}]
    engine.connect.assert_called_once()


@patch("app.services.org_units_admin_service._audit_org_unit_event")
@patch("app.services.org_units_admin_service._normalize_bulk_delete_roots")
@patch("app.services.org_units_admin_service._ORG_UNITS")
def test_bulk_delete_returns_not_found_for_missing_root(
    mock_org_units,
    mock_normalize,
    _mock_audit,
    mock_engine,
):
    engine, _conn = mock_engine
    mock_normalize.return_value = ([999], [])
    mock_org_units.get_org_unit.return_value = None

    result = bulk_delete_admin_org_units(actor_user_id=99, unit_ids=[999], db_engine=engine)

    assert result["deleted_ids"] == []
    assert result["failed"][0]["reason_code"] == "NOT_FOUND"
