from __future__ import annotations

import csv
import importlib.util
import inspect
from pathlib import Path
import sys


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


def test_loader_apply_path_uses_transaction_bound_order_and_contact_services():
    loader = _loader_module()
    source = inspect.getsource(loader.apply_one)

    assert "create_personnel_order_draft_tx" in source
    assert "create_personnel_order_item_tx" in source
    assert "register_personnel_order_tx" in source
    assert "ensure_operational_contact_for_employee" in source


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
