from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.sync_org_units_name_kk import (
    REQUIRED_ORG_UNITS_COLUMNS,
    SyncSafetyError,
    assert_org_units_schema,
    load_package,
    make_plan,
)


PACKAGE = Path(__file__).resolve().parents[1] / "reference-data" / "org_units_name_kk.json"


def target_rows(items: list[dict[str, str]]) -> list[dict[str, object]]:
    return [
        {
            "unit_id": index,
            "code": item["code"],
            "name": f"Unit {index}",
            "group_id": index % 4,
            "name_kk": item["name_kk"],
            "document_genitive_kk": f"Form {index}",
        }
        for index, item in enumerate(items, start=1)
    ]


def test_confirmed_package_has_46_unique_nonempty_code_name_pairs() -> None:
    items = load_package(PACKAGE)

    assert len(items) == 46
    assert len({item["code"].casefold() for item in items}) == 46
    assert all(item["code"] and item["name_kk"] for item in items)
    assert "ORG_MAIN" not in {item["code"] for item in items}


def test_matching_target_is_a_zero_update_dry_run_plan() -> None:
    items = load_package(PACKAGE)
    plan = make_plan(items, target_rows(items))

    assert plan["missing_codes"] == []
    assert plan["ambiguous_codes"] == {}
    assert plan["summary"] == {
        "package_items": 46,
        "matched": 46,
        "updates": 0,
        "already_matching": 46,
        "missing": 0,
        "ambiguous": 0,
    }


def test_plan_reports_missing_and_ambiguous_codes_without_selecting_a_target() -> None:
    items = load_package(PACKAGE)
    rows = target_rows(items[1:])
    duplicate = dict(rows[0])
    duplicate["unit_id"] = 999
    rows.append(duplicate)

    plan = make_plan(items, rows)

    assert plan["missing_codes"] == [items[0]["code"]]
    assert list(plan["ambiguous_codes"]) == [items[1]["code"]]
    assert plan["summary"]["matched"] == 44


def test_package_loader_rejects_duplicate_codes(tmp_path: Path) -> None:
    payload = json.loads(PACKAGE.read_text(encoding="utf-8"))
    payload["items"].append(dict(payload["items"][0], code=payload["items"][0]["code"].lower()))
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(SyncSafetyError, match="duplicate package codes"):
        load_package(path)


class _SchemaResult:
    def __init__(self, columns: set[str]) -> None:
        self._columns = columns

    def mappings(self) -> list[dict[str, str]]:
        return [{"column_name": column} for column in self._columns]


class _SchemaConnection:
    def __init__(self, columns: set[str]) -> None:
        self._columns = columns

    def execute(self, _statement: object) -> _SchemaResult:
        return _SchemaResult(self._columns)


def test_schema_preflight_names_missing_columns_before_any_org_units_query() -> None:
    columns = set(REQUIRED_ORG_UNITS_COLUMNS) - {"name_kk", "document_genitive_kk"}

    with pytest.raises(SyncSafetyError, match="document_genitive_kk, name_kk"):
        assert_org_units_schema(_SchemaConnection(columns))


def test_schema_preflight_accepts_the_complete_schema() -> None:
    assert_org_units_schema(_SchemaConnection(set(REQUIRED_ORG_UNITS_COLUMNS)))
