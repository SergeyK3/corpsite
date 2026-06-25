"""OPS-026.4a — targeted backfill mode for operational contacts."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_PATH = ROOT / "scripts" / "ops" / "ops026_backfill_operational_contacts.py"


def _load_ops_module():
    spec = importlib.util.spec_from_file_location(
        "ops026_backfill_operational_contacts",
        _SCRIPT_PATH,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ops = _load_ops_module()


@pytest.mark.parametrize(
    ("apply", "user_id", "employee_id", "expected"),
    [
        (True, None, None, True),
        (True, 17, None, False),
        (True, None, 44, False),
        (True, 17, 44, False),
        (False, None, None, False),
        (False, 17, None, False),
    ],
)
def test_apply_requires_target_filter(apply, user_id, employee_id, expected):
    assert ops._apply_requires_target_filter(
        apply=apply,
        user_id=user_id,
        employee_id=employee_id,
    ) is expected


def test_filter_candidates_by_user_id():
    candidates = [
        {"user_id": 10, "employee_id": 7, "full_name": "Smoke"},
        {"user_id": 17, "employee_id": 44, "full_name": "Nurbekov"},
    ]
    filtered = ops._filter_candidates(candidates, user_id=17, employee_id=None)
    assert filtered == [candidates[1]]


def test_filter_candidates_by_employee_id():
    candidates = [
        {"user_id": 10, "employee_id": 7, "full_name": "Smoke"},
        {"user_id": 17, "employee_id": 44, "full_name": "Nurbekov"},
    ]
    filtered = ops._filter_candidates(candidates, user_id=None, employee_id=44)
    assert filtered == [candidates[1]]


def test_filter_candidates_no_filter_returns_all():
    candidates = [
        {"user_id": 10, "employee_id": 7, "full_name": "Smoke"},
        {"user_id": 17, "employee_id": 44, "full_name": "Nurbekov"},
    ]
    assert ops._filter_candidates(candidates, user_id=None, employee_id=None) == candidates


def test_main_apply_without_filter_exits_nonzero(monkeypatch):
    monkeypatch.setattr(
        "sys.stderr",
        __import__("io").StringIO(),
    )
    assert ops.main(["--apply"]) == 2
