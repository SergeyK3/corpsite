"""ADR-038 Phase D.1 — HR sync admin API tests."""
from __future__ import annotations

import base64
import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.employee_import_profile_override_service import (
    employee_overrides_available,
    upsert_employee_override,
)
from app.services.sync.conflict_policy import CONFLICT_TYPE_SECTION_OVERLAP
from app.services.sync.package_schema import (
    PACKAGE_VERSION,
    SCHEMA_VERSION,
    EmployeeImportProfileOverrideSyncRecord,
    EmployeeSyncRecord,
    build_employee_key,
)
from app.services.sync.package_writer import write_sync_package
from tests.conftest import auth_headers, get_columns, insert_returning_id


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_sync_tables() -> None:
    with engine.connect() as conn:
        if not employee_overrides_available(conn):
            pytest.skip("employee_import_profile_overrides not available — run alembic upgrade head")


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def client():
    return TestClient(app)


def _create_employee(conn, *, full_name: str, org_unit_id: int) -> int:
    cols = get_columns(conn, "employees")
    values = {"full_name": full_name}
    if "org_unit_id" in cols:
        values["org_unit_id"] = org_unit_id
    if "is_active" in cols:
        values["is_active"] = True
    return insert_returning_id(conn, table="employees", id_col="employee_id", values=values)


def _attach_iin(conn, *, employee_id: int, iin_value: str, created_by: int) -> None:
    insert_returning_id(
        conn,
        table="employee_identities",
        id_col="identity_id",
        values={
            "employee_id": employee_id,
            "identity_type": "IIN",
            "identity_value": iin_value,
            "is_primary": True,
            "created_by": created_by,
        },
    )


def _write_package(
    tmp_path: Path,
    *,
    employees: list[EmployeeSyncRecord],
    overrides: list[EmployeeImportProfileOverrideSyncRecord],
    stamp: str = "20260617_160000",
) -> Path:
    exported_at = datetime.strptime(stamp, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
    result = write_sync_package(
        tmp_path,
        source_instance_id="vps-pilot",
        source_organization={"id": "org-1", "name": "Test Org"},
        employees=employees,
        overrides=overrides,
        exported_at=exported_at,
    )
    return Path(result.output_path)


def _random_iin() -> str:
    return f"{int(uuid4().int % 10**12):012d}"


def _cleanup_employee(employee_id: int | None) -> None:
    if not employee_id:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.employee_import_profile_overrides WHERE employee_id = :id"),
            {"id": employee_id},
        )
        conn.execute(
            text("DELETE FROM public.employee_identities WHERE employee_id = :id"),
            {"id": employee_id},
        )
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id = :id"),
            {"id": employee_id},
        )


def _seed_sync_employee(seed, *, full_name: str, iin: str, profile: dict) -> int:
    employee_id: int | None = None
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn,
                full_name=full_name,
                org_unit_id=seed["unit_id"],
            )
            _attach_iin(
                conn,
                employee_id=employee_id,
                iin_value=iin,
                created_by=seed["initiator_user_id"],
            )
            upsert_employee_override(
                conn,
                employee_id=employee_id,
                profile=profile,
                updated_by=seed["initiator_user_id"],
            )
        assert employee_id is not None
        return employee_id
    except Exception:
        _cleanup_employee(employee_id)
        raise


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_sync_meta_api(client: TestClient, privileged_headers):
    _require_sync_tables()
    resp = client.get("/directory/personnel/sync/meta", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["package_version"] == PACKAGE_VERSION


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_sync_meta_forbidden_without_privilege(client: TestClient, seed):
    _require_sync_tables()
    resp = client.get("/directory/personnel/sync/meta", headers=auth_headers(seed["executor_user_id"]))
    assert resp.status_code == 403


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_sync_export_api(client: TestClient, privileged_headers, seed, tmp_path: Path):
    _require_sync_tables()
    suffix = uuid4().hex[:8]
    iin = _random_iin()
    employee_id: int | None = None
    try:
        employee_id = _seed_sync_employee(
            seed,
            full_name=f"Sync Export {suffix}",
            iin=iin,
            profile={"notes": [{"text": f"export-{suffix}"}]},
        )

        resp = client.post(
            "/directory/personnel/sync/export",
            headers={**privileged_headers, "Content-Type": "application/json"},
            json={
                "source_instance_id": "vps-pilot",
                "source_organization_id": "org-test",
                "source_organization_name": "Test Hospital",
                "environment": "server",
                "notes": "api test",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["validation_ok"] is True
        assert body["employee_count"] >= 1
        assert body["override_count"] >= 1
        assert body["package_name"].endswith(".zip")
        assert body["package_base64"]

        zip_bytes = base64.b64decode(body["package_base64"])
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            names = set(archive.namelist())
            assert "manifest.json" in names
            assert "employees.jsonl" in names
            assert "employee_import_profile_overrides.jsonl" in names
    finally:
        _cleanup_employee(employee_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_sync_preview_api_identical(client: TestClient, privileged_headers, seed, tmp_path: Path):
    _require_sync_tables()
    suffix = uuid4().hex[:8]
    iin = _random_iin()
    full_name = f"Sync Preview {suffix}"
    employee_key = build_employee_key(iin=iin, full_name=full_name)
    employee_id: int | None = None
    try:
        employee_id = _seed_sync_employee(
            seed,
            full_name=full_name,
            iin=iin,
            profile={"notes": [{"text": f"preview-{suffix}"}]},
        )

        stamp = "20260617_170000"
        exported_at = datetime.strptime(stamp, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
        package_path = _write_package(
            tmp_path,
            employees=[
                EmployeeSyncRecord(
                    employee_key=employee_key,
                    source_employee_id=employee_id,
                    full_name=full_name,
                    iin=iin,
                    status="active",
                )
            ],
            overrides=[
                EmployeeImportProfileOverrideSyncRecord(
                    employee_key=employee_key,
                    profile_override={"notes": [{"text": f"preview-{suffix}"}]},
                    profile_status="active",
                    profile_review_status="pending",
                    created_at=exported_at.isoformat(),
                    updated_at=exported_at.isoformat(),
                    source_employee_id=employee_id,
                )
            ],
            stamp=stamp,
        )

        with package_path.open("rb") as fh:
            resp = client.post(
                "/directory/personnel/sync/preview",
                headers=privileged_headers,
                files={"file": (package_path.name, fh, "application/zip")},
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["validation_ok"] is True
        assert body["identical_count"] == 1
        assert body["apply_allowed_count"] == 0
        assert len(body["items"]) == 1
        item = body["items"][0]
        assert item["employee_key"] == employee_key
        assert item["employee_name"] == full_name
        assert item["status"] == "identical"
        assert item["action"] == "skip"
        assert item["apply_allowed"] is False
    finally:
        _cleanup_employee(employee_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_sync_preview_api_conflict_rendering_fields(client: TestClient, privileged_headers, seed, tmp_path: Path):
    _require_sync_tables()
    suffix = uuid4().hex[:8]
    iin = _random_iin()
    full_name = f"Sync Conflict {suffix}"
    employee_key = build_employee_key(iin=iin, full_name=full_name)
    employee_id: int | None = None
    try:
        employee_id = _seed_sync_employee(
            seed,
            full_name=full_name,
            iin=iin,
            profile={
                "certificates": [{"kind": "target"}],
            },
        )

        stamp = "20260617_180000"
        exported_at = datetime.strptime(stamp, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
        package_path = _write_package(
            tmp_path,
            employees=[
                EmployeeSyncRecord(
                    employee_key=employee_key,
                    source_employee_id=employee_id,
                    full_name=full_name,
                    iin=iin,
                    status="active",
                )
            ],
            overrides=[
                EmployeeImportProfileOverrideSyncRecord(
                    employee_key=employee_key,
                    profile_override={"certificates": [{"kind": "incoming"}]},
                    profile_status="active",
                    profile_review_status="pending",
                    created_at=exported_at.isoformat(),
                    updated_at=exported_at.isoformat(),
                    source_employee_id=employee_id,
                )
            ],
            stamp=stamp,
        )

        with package_path.open("rb") as fh:
            resp = client.post(
                "/directory/personnel/sync/preview",
                headers=privileged_headers,
                files={"file": (package_path.name, fh, "application/zip")},
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["conflict_count"] == 1
        item = body["items"][0]
        assert item["status"] == "conflict"
        assert item["action"] == "review_required"
        assert item["apply_allowed"] is False
        assert item["conflict_type"] == CONFLICT_TYPE_SECTION_OVERLAP
        assert item["employee_name"] == full_name
        assert item["conflict_sections"]
    finally:
        _cleanup_employee(employee_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_sync_preview_table_contract(client: TestClient, privileged_headers, seed, tmp_path: Path):
    """UI table contract — required columns present on each preview item."""
    _require_sync_tables()
    suffix = uuid4().hex[:8]
    iin = _random_iin()
    full_name = f"Sync Table {suffix}"
    employee_key = build_employee_key(iin=iin, full_name=full_name)
    employee_id: int | None = None
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(conn, full_name=full_name, org_unit_id=seed["unit_id"])
            _attach_iin(
                conn,
                employee_id=employee_id,
                iin_value=iin,
                created_by=seed["initiator_user_id"],
            )

        stamp = "20260617_190000"
        exported_at = datetime.strptime(stamp, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
        package_path = _write_package(
            tmp_path,
            employees=[
                EmployeeSyncRecord(
                    employee_key=employee_key,
                    source_employee_id=employee_id,
                    full_name=full_name,
                    iin=iin,
                    status="active",
                )
            ],
            overrides=[
                EmployeeImportProfileOverrideSyncRecord(
                    employee_key=employee_key,
                    profile_override={"notes": [{"text": "new-from-package"}]},
                    profile_status="active",
                    profile_review_status="pending",
                    created_at=exported_at.isoformat(),
                    updated_at=exported_at.isoformat(),
                    source_employee_id=employee_id,
                )
            ],
            stamp=stamp,
        )

        with package_path.open("rb") as fh:
            resp = client.post(
                "/directory/personnel/sync/preview",
                headers=privileged_headers,
                files={"file": (package_path.name, fh, "application/zip")},
            )
        assert resp.status_code == 200, resp.text
        item = resp.json()["items"][0]
        for key in (
            "employee_key",
            "employee_name",
            "status",
            "action",
            "changed_sections",
            "reason",
            "apply_allowed",
        ):
            assert key in item
    finally:
        _cleanup_employee(employee_id)
