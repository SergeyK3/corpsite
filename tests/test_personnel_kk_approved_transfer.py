"""Approval integrity and fail-closed guards for the portable KK transfer."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from uuid import uuid4

import pytest

from scripts.transfer_personnel_kk_approved_20261118 import (
    PACKAGE, ROOT, TransferError, compare, read_package, save_backup,
)


def baseline(package):
    positions = {}
    for item in package["positions"]:
        expected = item["expected"]
        positions[expected["position_id"]] = {
            "row": {key: value for key, value in expected.items() if key != "job_code"},
            "job_code": expected["job_code"],
        }
    return positions, dict(package["org_units"][0]["expected"])


def test_approved_package_matches_28_source_rows_and_extra_approvals():
    package, _ = read_package(PACKAGE)
    source = json.loads((ROOT / "reference-data/dictionaries/positions-kk-approved-20261118.json").read_text(encoding="utf-8"))
    by_local_id = {row["source_local_id"]: row for row in package["positions"]}
    assert len(source["items"]) == 28
    assert len(by_local_id) == 29
    for source_row in source["items"]:
        target_row = by_local_id[source_row["position_id"]]
        assert target_row["expected"]["name"] == source_row["name"]
        assert target_row["set"]["name_kk"] == source_row["name_kk"]
    assert by_local_id[27]["expected"]["name"] == "Медсестра"
    assert by_local_id[27]["set"]["name_kk"] == "Мейіргер"
    assert by_local_id[27]["set"]["document_possessive_kk"] == "мейіргері"
    assert package["org_units"][0]["set"]["name_kk"] == "Көпсалалы медицина орталығы"


def test_approved_checksum_accepts_windows_line_endings():
    path = ROOT / "runtime" / f"personnel-kk-transfer-crlf-{uuid4().hex}.json"
    try:
        path.write_bytes(PACKAGE.read_bytes().replace(b"\n", b"\r\n"))
        assert read_package(path)[1] == read_package(PACKAGE)[1]
    finally:
        path.unlink(missing_ok=True)


def test_all_rows_must_match_before_any_update():
    package, _ = read_package(PACKAGE)
    positions, org = baseline(package)
    compare(package, positions, org)
    modified = copy.deepcopy(positions)
    modified[package["positions"][0]["expected"]["position_id"]]["row"]["name"] = "changed"
    with pytest.raises(TransferError, match="source drift: name"):
        compare(package, modified, org)
    with pytest.raises(TransferError, match="Org-unit source drift"):
        compare(package, positions, {**org, "name_kk": "changed"})


def test_backup_contains_prestate_and_refuses_overwrite():
    package, digest = read_package(PACKAGE)
    positions, org = baseline(package)
    path = ROOT / "runtime" / f"personnel-kk-transfer-test-{uuid4().hex}.json"
    try:
        save_backup(path, digest, positions, org)
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["package_sha256"] == digest
        assert len(saved["positions"]) == 29
        with pytest.raises(FileExistsError):
            save_backup(path, digest, positions, org)
    finally:
        path.unlink(missing_ok=True)
