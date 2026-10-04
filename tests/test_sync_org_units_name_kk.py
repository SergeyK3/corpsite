from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.sync_org_units_name_kk import (
    REQUIRED_ORG_UNITS_COLUMNS,
    SyncSafetyError,
    assert_safe,
    assert_org_units_schema,
    load_code_mappings,
    load_package,
    make_plan,
)


PACKAGE = Path(__file__).resolve().parents[1] / "reference-data" / "org_units_name_kk.json"
MAPPINGS = Path(__file__).resolve().parents[1] / "reference-data" / "org_units_name_kk_server_code_mappings.json"


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
        "package_items": 46, "matched": 46, "updates": 0, "already_matching": 46,
        "missing": 0, "ambiguous": 0, "alias_source_conflicts": 0, "alias_name_mismatches": 0,
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


def test_explicit_qm_server_mapping_matches_only_the_expected_server_row() -> None:
    items = load_package(PACKAGE)
    mappings = load_code_mappings(MAPPINGS, items)
    rows = [row for row in target_rows(items) if row["code"] != "QM"]
    rows.append({
        "unit_id": 44, "code": "qm_ovipd", "name": "Отдел менеджмента и качества", "group_id": 3,
        "name_kk": None, "document_genitive_kk": None,
    })

    plan = make_plan(items, rows, mappings)

    assert plan["summary"]["matched"] == 46
    assert plan["summary"]["updates"] == 1
    assert plan["summary"]["alias_source_conflicts"] == 0
    assert plan["summary"]["alias_name_mismatches"] == 0
    qm = next(item for item in plan["items"] if item["code"] == "QM")
    assert qm["unit_id"] == 44
    assert qm["database_code"] == "qm_ovipd"
    assert qm["mapped"] is True


def test_explicit_qm_mapping_blocks_both_codes_or_a_different_russian_name() -> None:
    items = load_package(PACKAGE)
    mappings = load_code_mappings(MAPPINGS, items)
    both_codes = target_rows(items)
    both_codes.append({
        "unit_id": 44, "code": "qm_ovipd", "name": "Отдел менеджмента и качества", "group_id": 3,
        "name_kk": None, "document_genitive_kk": None,
    })
    conflict = make_plan(items, both_codes, mappings)
    assert "QM" in conflict["alias_source_conflicts"]
    with pytest.raises(SyncSafetyError):
        assert_safe(conflict)

    wrong_name = [row for row in target_rows(items) if row["code"] != "QM"]
    wrong_name.append({
        "unit_id": 44, "code": "qm_ovipd", "name": "Другое название", "group_id": 3,
        "name_kk": None, "document_genitive_kk": None,
    })
    mismatch = make_plan(items, wrong_name, mappings)
    assert mismatch["alias_name_mismatches"]["QM"]["actual_name"] == "Другое название"
    with pytest.raises(SyncSafetyError):
        assert_safe(mismatch)


def test_mapping_loader_rejects_a_target_that_intersects_another_package_code(tmp_path: Path) -> None:
    payload = {
        "schema_version": 1,
        "mappings": [{"package_code": "QM", "server_code": "DISP", "expected_name": "Отдел менеджмента и качества"}],
    }
    path = tmp_path / "overlap.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(SyncSafetyError, match="mapping target intersects package code"):
        load_code_mappings(path, load_package(PACKAGE))
