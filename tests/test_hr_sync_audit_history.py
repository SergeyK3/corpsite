"""ADR-038 Phase D.4 — E2E sync audit history verification.

Validates that export, preview, and apply operations persist audit records
with expected fields and appear in GET /directory/personnel/sync/history
(newest first).
"""
from __future__ import annotations

import base64
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.sync.audit_service import sync_audit_log_available
from app.services.sync.package_schema import (
    EmployeeImportProfileOverrideSyncRecord,
    EmployeeSyncRecord,
    build_employee_key,
)
from tests.conftest import auth_headers
from tests.test_hr_sync_api import (
    _cleanup_employee,
    _db_available,
    _post_sync_apply,
    _random_iin,
    _require_sync_audit_log,
    _seed_sync_employee,
    _write_package,
)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def client():
    return TestClient(app)


def _history_count(client: TestClient, headers: dict) -> int:
    resp = client.get("/directory/personnel/sync/history?limit=1", headers=headers)
    assert resp.status_code == 200, resp.text
    return int(resp.json()["total"])


def _find_history_item(items: list[dict], sync_audit_id: int) -> dict:
    for item in items:
        if item["sync_audit_id"] == sync_audit_id:
            return item
    raise AssertionError(f"sync_audit_id={sync_audit_id} not found in history items")


def _assert_iso_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None or "T" in value
    return parsed


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_full_sync_cycle_audit_history_e2e(
    client: TestClient,
    privileged_headers,
    seed,
    tmp_path: Path,
):
    """Export → preview → apply writes three audit rows retrievable via history API."""
    _require_sync_audit_log()
    suffix = uuid4().hex[:8]
    iin = _random_iin()
    full_name = f"Sync Audit E2E {suffix}"
    employee_key = build_employee_key(iin=iin, full_name=full_name)
    employee_id: int | None = None
    actor_user_id = seed["initiator_user_id"]

    try:
        profile = {"notes": [{"text": f"audit-e2e-{suffix}"}]}
        employee_id = _seed_sync_employee(seed, full_name=full_name, iin=iin, profile=profile)

        total_before = _history_count(client, privileged_headers)

        export_resp = client.post(
            "/directory/personnel/sync/export",
            headers={**privileged_headers, "Content-Type": "application/json"},
            json={
                "source_instance_id": "vps-pilot-d4",
                "source_organization_id": "org-d4",
                "source_organization_name": "D4 Verification Org",
                "environment": "server",
                "notes": f"d4-export-{suffix}",
            },
        )
        assert export_resp.status_code == 200, export_resp.text
        export_body = export_resp.json()
        export_audit_id = export_body.get("audit_id")
        assert export_audit_id, "export must return audit_id"
        package_name = export_body["package_name"]

        zip_bytes = base64.b64decode(export_body["package_base64"])
        package_path = tmp_path / package_name
        package_path.write_bytes(zip_bytes)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            assert "manifest.json" in set(archive.namelist())

        with package_path.open("rb") as fh:
            preview_resp = client.post(
                "/directory/personnel/sync/preview",
                headers=privileged_headers,
                files={"file": (package_path.name, fh, "application/zip")},
            )
        assert preview_resp.status_code == 200, preview_resp.text
        preview_body = preview_resp.json()
        preview_audit_id = preview_body.get("audit_id")
        assert preview_audit_id, "preview must return audit_id"
        assert preview_body["identical_count"] >= 1

        apply_resp = _post_sync_apply(
            client,
            privileged_headers,
            package_path,
            dry_run=False,
            notes=f"d4-apply-{suffix}",
        )
        assert apply_resp.status_code == 200, apply_resp.text
        apply_body = apply_resp.json()
        apply_audit_id = apply_body.get("audit_id")
        assert apply_audit_id, "apply must return audit_id"

        history_resp = client.get(
            "/directory/personnel/sync/history?limit=20",
            headers=privileged_headers,
        )
        assert history_resp.status_code == 200, history_resp.text
        history_body = history_resp.json()

        assert history_body["audit_log_available"] is True
        assert history_body["total"] >= total_before + 3

        items = history_body["items"]
        assert len(items) >= 3

        # Newest first: apply should appear before preview before export in this cycle.
        cycle_ids = {export_audit_id, preview_audit_id, apply_audit_id}
        cycle_items = [item for item in items if item["sync_audit_id"] in cycle_ids]
        assert len(cycle_items) == 3

        apply_item = _find_history_item(items, apply_audit_id)
        preview_item = _find_history_item(items, preview_audit_id)
        export_item = _find_history_item(items, export_audit_id)

        apply_idx = items.index(apply_item)
        preview_idx = items.index(preview_item)
        export_idx = items.index(export_item)
        assert apply_idx < preview_idx < export_idx, "history must be newest-first for this cycle"

        apply_ts = _assert_iso_timestamp(apply_item["happened_at"])
        preview_ts = _assert_iso_timestamp(preview_item["happened_at"])
        export_ts = _assert_iso_timestamp(export_item["happened_at"])
        assert apply_ts >= preview_ts >= export_ts

        for item in (export_item, preview_item, apply_item):
            assert item["actor_user_id"] == actor_user_id
            assert item["validation_ok"] is True
            assert isinstance(item["summary"], dict) and item["summary"]

        assert export_item["operation"] == "export"
        assert export_item["notes"] == f"d4-export-{suffix}"
        assert export_item["context"]["source_instance_id"] == "vps-pilot-d4"
        assert export_item["summary"]["employee_count"] >= 1
        assert export_item["summary"]["override_count"] >= 1
        assert export_item["package_name"] == package_name

        assert preview_item["operation"] == "preview"
        assert preview_item["package_name"] == package_name
        assert preview_item["summary"]["identical_count"] >= 1
        assert preview_item["summary"]["total_records"] >= 1

        assert apply_item["operation"] == "apply"
        assert apply_item["dry_run"] is False
        assert apply_item["notes"] == f"d4-apply-{suffix}"
        assert apply_item["package_name"] == package_name
        assert apply_item["summary"]["identical"] >= 1

        # Linkage: each operation audit_id maps to its own history row (no preview_id/apply_id FK).
        for audit_id, op in (
            (export_audit_id, "export"),
            (preview_audit_id, "preview"),
            (apply_audit_id, "apply"),
        ):
            detail_resp = client.get(
                f"/directory/personnel/sync/history/{audit_id}",
                headers=privileged_headers,
            )
            assert detail_resp.status_code == 200, detail_resp.text
            detail = detail_resp.json()
            assert detail["sync_audit_id"] == audit_id
            assert detail["operation"] == op
            assert "warnings" in detail

        # Persist sample for D.4 report (stdout in pytest -q -s).
        sample = {
            "cycle_suffix": suffix,
            "audit_ids": {
                "export": export_audit_id,
                "preview": preview_audit_id,
                "apply": apply_audit_id,
            },
            "history_list_head": items[:3],
        }
        print("\n--- ADR-038 D.4 history sample ---")
        print(json.dumps(sample, ensure_ascii=False, indent=2, default=str))
    finally:
        _cleanup_employee(employee_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_history_empty_state_before_first_record(client: TestClient, privileged_headers):
    """History API returns audit_log_available and numeric total (UI empty state uses items.length)."""
    _require_sync_audit_log()
    resp = client.get("/directory/personnel/sync/history?limit=5", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["audit_log_available"] is True
    assert isinstance(body["total"], int)
    assert isinstance(body["items"], list)
    if body["total"] == 0:
        assert body["items"] == []


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_audit_table_columns_match_api_contract(client: TestClient, privileged_headers, seed, tmp_path: Path):
    """DB row fields align with API names (operation, happened_at, actor_user_id, summary, context)."""
    _require_sync_audit_log()
    suffix = uuid4().hex[:8]
    employee_id: int | None = None
    try:
        employee_id = _seed_sync_employee(
            seed,
            full_name=f"Sync Schema {suffix}",
            iin=_random_iin(),
            profile={"notes": [{"text": f"schema-{suffix}"}]},
        )
        client.post(
            "/directory/personnel/sync/export",
            headers={**privileged_headers, "Content-Type": "application/json"},
            json={
                "source_instance_id": "schema-check",
                "source_organization_id": "org-schema",
                "source_organization_name": "Schema Org",
                "environment": "local",
            },
        )

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT operation, happened_at, actor_user_id, summary, context
                    FROM public.hr_sync_audit_log
                    WHERE operation = 'export'
                    ORDER BY sync_audit_id DESC
                    LIMIT 1
                    """
                )
            ).first()
        assert row is not None
        assert row.operation == "export"
        assert row.happened_at is not None
        assert row.actor_user_id == seed["initiator_user_id"]
        context = row.context if isinstance(row.context, dict) else json.loads(row.context)
        assert context.get("source_instance_id") == "schema-check"
    finally:
        _cleanup_employee(employee_id)
