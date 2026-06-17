"""ADR-038 Phase C.1 — conflict policy and apply gate tests."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.employee_import_profile_override_service import (
    employee_overrides_available,
    load_employee_override,
    upsert_employee_override,
)
from app.services.sync.conflict_policy import (
    CONFLICT_TYPE_SECTION_OVERLAP,
    CONFLICT_TYPE_TARGET_NEWER,
    STATUS_CONFLICT,
    STATUS_MERGE,
    STATUS_NEW,
    STATUS_UPDATE,
    classify_sync_override,
    merge_profile_overrides,
)
from app.services.sync.import_service import import_hr_sync_package
from app.services.sync.package_schema import EmployeeImportProfileOverrideSyncRecord
from app.services.sync.preview_service import preview_hr_sync_package
from app.services.sync.package_schema import EmployeeSyncRecord
from app.services.sync.package_writer import write_sync_package
from tests.conftest import get_columns, insert_returning_id


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_phase_c1() -> None:
    with engine.connect() as conn:
        if not employee_overrides_available(conn):
            pytest.skip("employee_import_profile_overrides not available — run alembic upgrade head")


def _record(
    *,
    employee_key: str,
    profile_override: dict,
    updated_at: str = "2026-06-10T10:00:00+00:00",
) -> EmployeeImportProfileOverrideSyncRecord:
    return EmployeeImportProfileOverrideSyncRecord(
        employee_key=employee_key,
        profile_override=profile_override,
        updated_at=updated_at,
    )


def test_section_overlap_conflict_even_when_incoming_newer() -> None:
    incoming = _record(
        employee_key="iin:900101300123",
        profile_override={"certificates": [{"kind": "B"}]},
        updated_at="2026-06-20T10:00:00+00:00",
    )
    target = {
        "profile_override": {"certificates": [{"kind": "A"}]},
        "updated_at": "2026-06-01T10:00:00+00:00",
    }
    result = classify_sync_override(incoming, target_override=target)
    assert result.status == STATUS_CONFLICT
    assert result.conflict_type == CONFLICT_TYPE_SECTION_OVERLAP
    assert result.conflict_sections == ["certificates"]
    assert result.apply_allowed is False


def test_target_newer_conflict() -> None:
    incoming = _record(
        employee_key="iin:900101300123",
        profile_override={"notes": "incoming"},
        updated_at="2026-06-10T10:00:00+00:00",
    )
    target = {
        "profile_override": {"training": [{"topic": "target only"}]},
        "updated_at": "2026-06-20T10:00:00+00:00",
    }
    result = classify_sync_override(incoming, target_override=target)
    assert result.status == STATUS_CONFLICT
    assert result.conflict_type == CONFLICT_TYPE_TARGET_NEWER


def test_disjoint_sections_classified_as_merge() -> None:
    incoming = _record(
        employee_key="iin:900101300123",
        profile_override={"certificates": [{"kind": "B"}]},
    )
    target = {
        "profile_override": {"training": [{"topic": "T"}]},
        "updated_at": "2026-06-08T10:00:00+00:00",
    }
    result = classify_sync_override(incoming, target_override=target)
    assert result.status == STATUS_MERGE
    assert result.apply_allowed is True
    assert result.merged_profile_override is not None
    assert "certificates" in result.merged_profile_override
    assert "training" in result.merged_profile_override


def test_merge_profile_overrides_unions_sections() -> None:
    merged = merge_profile_overrides(
        {"training": [{"topic": "keep"}]},
        {"certificates": [{"kind": "new"}]},
    )
    assert merged["training"] == [{"topic": "keep"}]
    assert merged["certificates"] == [{"kind": "new"}]


@pytest.fixture
def apply_gate_fixture(seed, tmp_path: Path):
    _require_phase_c1()
    suffix = uuid4().hex[:8]
    iin_merge = f"{int(uuid4().int % 10**12):012d}"
    iin_conflict = f"{int(uuid4().int % 10**12):012d}"
    user_id = int(seed["initiator_user_id"])
    unit_id = int(seed["unit_id"])
    employee_merge: int | None = None
    employee_conflict: int | None = None

    try:
        with engine.begin() as conn:
            employee_merge = _create_employee(conn, full_name=f"Merge {suffix}", org_unit_id=unit_id)
            _attach_iin(conn, employee_id=employee_merge, iin_value=iin_merge, created_by=user_id)
            upsert_employee_override(
                conn,
                employee_merge,
                profile={"training": [{"topic": "target training"}]},
                updated_by=user_id,
            )
            conn.execute(
                text(
                    """
                    UPDATE public.employee_import_profile_overrides
                    SET updated_at = :updated_at
                    WHERE employee_id = :employee_id
                    """
                ),
                {
                    "employee_id": employee_merge,
                    "updated_at": datetime(2026, 6, 8, 10, 0, tzinfo=timezone.utc),
                },
            )

            employee_conflict = _create_employee(conn, full_name=f"Conflict {suffix}", org_unit_id=unit_id)
            _attach_iin(conn, employee_id=employee_conflict, iin_value=iin_conflict, created_by=user_id)
            upsert_employee_override(
                conn,
                employee_conflict,
                profile={"certificates": [{"kind": "target"}]},
                updated_by=user_id,
            )
            conn.execute(
                text(
                    """
                    UPDATE public.employee_import_profile_overrides
                    SET updated_at = :updated_at
                    WHERE employee_id = :employee_id
                    """
                ),
                {
                    "employee_id": employee_conflict,
                    "updated_at": datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc),
                },
            )

        key_merge = f"iin:{iin_merge}"
        key_conflict = f"iin:{iin_conflict}"
        package_path = _write_package(
            tmp_path,
            employees=[
                EmployeeSyncRecord(employee_key=key_merge, full_name=f"Merge {suffix}", source_employee_id=employee_merge),
                EmployeeSyncRecord(
                    employee_key=key_conflict,
                    full_name=f"Conflict {suffix}",
                    source_employee_id=employee_conflict,
                    iin=iin_conflict,
                ),
            ],
            overrides=[
                _record(
                    employee_key=key_merge,
                    profile_override={"certificates": [{"kind": "incoming"}]},
                ),
                _record(
                    employee_key=key_conflict,
                    profile_override={"certificates": [{"kind": "incoming"}]},
                    updated_at="2026-06-10T10:00:00+00:00",
                ),
            ],
        )
        yield {
            "package_path": package_path,
            "employee_merge": employee_merge,
            "employee_conflict": employee_conflict,
            "key_merge": key_merge,
            "key_conflict": key_conflict,
        }
    finally:
        with engine.begin() as conn:
            for employee_id in (employee_merge, employee_conflict):
                if employee_id:
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


def _write_package(tmp_path: Path, *, employees, overrides) -> Path:
    result = write_sync_package(
        tmp_path,
        source_instance_id="vps-pilot",
        source_organization={"id": "org-pilot-1", "name": "City Hospital Pilot"},
        employees=employees,
        overrides=overrides,
        environment="local",
        exported_at=datetime(2026, 6, 17, 16, 0, 0, tzinfo=timezone.utc),
        allow_overwrite=True,
    )
    return Path(result.output_path)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_preview_and_import_share_policy_counts(apply_gate_fixture) -> None:
    package_path = apply_gate_fixture["package_path"]
    with engine.connect() as conn:
        preview = preview_hr_sync_package(conn, package_path=package_path)
        dry_run = import_hr_sync_package(conn, package_path=package_path, apply_changes=False)

    assert preview.merge_count == 1
    assert preview.conflict_count == 1
    assert preview.apply_allowed_count == 1
    assert dry_run.apply_allowed_count == 1
    assert dry_run.conflict_count == 1
    assert dry_run.merge_count == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_apply_gate_blocks_conflicts(apply_gate_fixture) -> None:
    package_path = apply_gate_fixture["package_path"]
    with engine.begin() as conn:
        result = import_hr_sync_package(conn, package_path=package_path, apply_changes=True)

    assert result.applied_count == 1
    assert result.blocked_count == 1
    assert result.conflict_count == 1

    with engine.connect() as conn:
        conflict_loaded = load_employee_override(conn, apply_gate_fixture["employee_conflict"])
        merge_loaded = load_employee_override(conn, apply_gate_fixture["employee_merge"])

    assert conflict_loaded is not None
    assert conflict_loaded["profile_override"]["certificates"][0]["kind"] == "target"
    assert merge_loaded is not None
    assert merge_loaded["profile_override"]["certificates"][0]["kind"] == "incoming"
    assert merge_loaded["profile_override"]["training"][0]["topic"] == "target training"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_new_override_still_applies_under_gate(apply_gate_fixture, seed, tmp_path: Path) -> None:
    suffix = uuid4().hex[:8]
    iin_value = f"{int(uuid4().int % 10**12):012d}"
    employee_id = None
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn,
                full_name=f"Fresh {suffix}",
                org_unit_id=int(seed["unit_id"]),
            )
            _attach_iin(
                conn,
                employee_id=employee_id,
                iin_value=iin_value,
                created_by=int(seed["initiator_user_id"]),
            )
        key = f"iin:{iin_value}"
        package_path = _write_package(
            tmp_path,
            employees=[
                EmployeeSyncRecord(
                    employee_key=key,
                    full_name=f"Fresh {suffix}",
                    source_employee_id=employee_id,
                    iin=iin_value,
                )
            ],
            overrides=[_record(employee_key=key, profile_override={"notes": "fresh"})],
        )
        with engine.begin() as conn:
            result = import_hr_sync_package(conn, package_path=package_path, apply_changes=True)
        assert result.applied_count == 1
        with engine.connect() as conn:
            loaded = load_employee_override(conn, employee_id)
        assert loaded is not None
        assert loaded["profile_override"]["notes"] == "fresh"
    finally:
        if employee_id:
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


def test_new_classification() -> None:
    incoming = _record(employee_key="iin:900101300123", profile_override={"notes": "x"})
    result = classify_sync_override(incoming, target_override=None)
    assert result.status == STATUS_NEW
    assert result.apply_allowed is True


def test_update_classification_when_source_newer() -> None:
    incoming = _record(
        employee_key="iin:900101300123",
        profile_override={"notes": "incoming"},
        updated_at="2026-06-15T10:00:00+00:00",
    )
    target = {
        "profile_override": {"training": [{"topic": "target"}]},
        "updated_at": "2026-06-10T10:00:00+00:00",
    }
    result = classify_sync_override(incoming, target_override=target)
    assert result.status == STATUS_MERGE
    assert result.apply_allowed is True
