"""Tests for missing-employee investigation helpers."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "investigate_hr_import_missing_employee.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("investigate_hr_import_missing_employee", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_kazakh_name_classified_as_employee_roster() -> None:
    mod = _load_module()
    audit = mod._parser_root_cause(
        "Әбитаев Ерхан Сайлаубекулы",
        iin_digits="800115300290",
    )
    assert audit["looks_like_person_name"] is True
    assert audit["infer_row_type"]["row_type"] == "EMPLOYEE"
    assert audit["infer_row_type"]["is_employee_roster"] is True


def test_russian_spelling_classified_as_employee_roster() -> None:
    mod = _load_module()
    audit = mod._parser_root_cause(
        "Абитаев Ерхан Сайлаубекулы",
        iin_digits="800115300290",
    )
    assert audit["looks_like_person_name"] is True
    assert audit["infer_row_type"]["row_type"] == "EMPLOYEE"
    assert audit["infer_row_type"]["is_employee_roster"] is True


def test_determine_verdict_lost_between_import_rows_and_normalized_records() -> None:
    mod = _load_module()
    verdict = mod.determine_verdict(
        import_rows=[
            {
                "row_id": 1,
                "normalized_payload": {
                    "full_name": "Әбитаев Ерхан Сайлаубекулы",
                    "iin": "800115300290",
                    "metadata": {
                        "row_type": "CATEGORY_ROW",
                        "is_employee_roster": False,
                        "classification": "CATEGORY_ROW",
                        "sheet_type": "doctors",
                    },
                }
            }
        ],
        normalized_records=[],
        canonical_entries=[],
        registry_employees=[{"employee_id": 24}],
        parser_audit={
            "target_rows": [
                {
                    "full_name": "Әбитаев Ерхан Сайлаубекулы",
                    "iin": "800115300290",
                    "looks_like_person_name": False,
                }
            ]
        },
    )
    assert verdict["stage"] == "lost_between_hr_import_rows_and_normalized_records"
    assert "CATEGORY_ROW" in verdict["normalization_skip_reason"]


def test_determine_verdict_lost_before_import_rows() -> None:
    mod = _load_module()
    verdict = mod.determine_verdict(
        import_rows=[],
        normalized_records=[],
        canonical_entries=[],
        registry_employees=[],
        parser_audit=None,
    )
    assert verdict["stage"] == "lost_before_hr_import_rows"
