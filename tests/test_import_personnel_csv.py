from __future__ import annotations

import csv
import importlib.util
import inspect
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _loader_module():
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(
            "import_personnel_csv_under_test", SCRIPTS / "import_personnel_csv.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


def test_production_order_number_is_stable_and_not_pilot_branded():
    loader = _loader_module()

    assert loader.order_number(source_row="185") == "PERSONNEL-IMPORT-2026-185"
    assert loader.order_number(source_row="00185") == "PERSONNEL-IMPORT-2026-185"
    assert "CSV-PILOT" not in loader.order_number(source_row="185")


def test_importer_uses_neutral_migration_labels_and_explicit_apply_actor():
    loader = _loader_module()
    source = inspect.getsource(loader)

    assert "PILOT_" not in source
    assert "csv-pilot" not in source
    assert "Local CSV pilot import" not in source
    assert "Bulk personnel migration" in source
    assert "--actor-user-id" in source
    assert "actor_user_exists" in source


def test_loader_apply_path_uses_transaction_bound_order_and_contact_services():
    loader = _loader_module()
    source = inspect.getsource(loader.apply_one)
    row_source = inspect.getsource(loader._row_from_source)

    assert "create_personnel_order_draft_tx" in source
    assert "create_personnel_order_item_tx" in source
    assert "register_personnel_order_tx" in source
    assert "ensure_operational_contact_for_employee" in source
    assert 'source.get("found_department_unit_id")' in row_source
    assert 'source.get("unit_id")' not in row_source


def test_apply_one_receives_actor_user_id_for_all_audit_writes():
    loader = _loader_module()
    source = inspect.getsource(loader.apply_one)

    assert "actor_user_id: int" in source
    assert "personnel-import:{actor_user_id}" in source
    assert "created_by=actor_user_id" in source


def test_apply_requires_explicit_actor_user_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    loader = _loader_module()
    csv_path = tmp_path / "source.csv"
    xlsx_path = tmp_path / "mapping.xlsx"
    report_path = tmp_path / "reconciliation.csv"
    output_path = tmp_path / "apply.csv"
    for path in (csv_path, xlsx_path, report_path):
        path.touch()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_personnel_csv.py",
            "--apply",
            "--csv",
            str(csv_path),
            "--xlsx",
            str(xlsx_path),
            "--report",
            str(report_path),
            "--output-report",
            str(output_path),
        ],
    )

    with pytest.raises(SystemExit, match="--apply requires --actor-user-id"):
        loader.main()

    monkeypatch.setattr(loader, "actor_user_exists", lambda actor_user_id: False)
    monkeypatch.setattr(sys, "argv", [*sys.argv, "--actor-user-id", "42"])
    with pytest.raises(SystemExit, match="--actor-user-id does not exist: 42"):
        loader.main()


def test_reconcile_requires_explicit_input_and_output_paths():
    reconcile_path = SCRIPTS / "reconcile_personnel_csv.py"
    source = reconcile_path.read_text(encoding="utf-8")

    assert 'parser.add_argument("--csv", type=Path, required=True' in source
    assert 'parser.add_argument("--xlsx", type=Path, required=True' in source
    assert 'parser.add_argument("--output-report", type=Path, required=True' in source
    assert 'ROOT / "tmp"' not in source


def test_load_source_rows_limits_to_new_rows_and_requested_resume_subset(tmp_path: Path):
    loader = _loader_module()
    report = tmp_path / "reconciliation.csv"
    with report.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["csv_row", "status"])
        writer.writeheader()
        writer.writerows(
            [
                {"csv_row": "10", "status": loader.STATUS_NEW},
                {"csv_row": "11", "status": "existing"},
                {"csv_row": "12", "status": loader.STATUS_NEW},
            ]
        )

    assert [row["csv_row"] for row in loader.load_source_rows(report)] == ["10", "12"]
    assert [row["csv_row"] for row in loader.load_source_rows(report, {12})] == ["12"]
