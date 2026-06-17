"""ADR-038 Phase B.4 — HR sync package preview engine tests."""
from __future__ import annotations

import json
import zipfile
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
from app.services.sync.conflict_policy import CONFLICT_TYPE_SECTION_OVERLAP
from app.services.sync.preview_service import preview_hr_sync_package
from app.services.sync.package_schema import (
    EmployeeImportProfileOverrideSyncRecord,
    EmployeeSyncRecord,
    build_employee_key,
)
from app.services.sync.package_writer import write_sync_package
from tests.conftest import get_columns, insert_returning_id


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_phase_b4() -> None:
    with engine.connect() as conn:
        if not employee_overrides_available(conn):
            pytest.skip("employee_import_profile_overrides not available — run alembic upgrade head")


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
        source_organization={"id": "org-pilot-1", "name": "City Hospital Pilot"},
        employees=employees,
        overrides=overrides,
        environment="local",
        exported_at=exported_at,
        allow_overwrite=True,
    )
    return Path(result.output_path)


def _employee_record(*, employee_key: str, full_name: str, source_id: int, iin: str | None = None) -> EmployeeSyncRecord:
    return EmployeeSyncRecord(
        employee_key=employee_key,
        source_employee_id=source_id,
        full_name=full_name,
        iin=iin,
        status="active",
    )


def _override_record(
    *,
    employee_key: str,
    profile_override: dict,
    updated_at: str = "2026-06-10T10:00:00+00:00",
) -> EmployeeImportProfileOverrideSyncRecord:
    return EmployeeImportProfileOverrideSyncRecord(
        employee_key=employee_key,
        profile_override=profile_override,
        created_at="2026-06-01T10:00:00+00:00",
        updated_at=updated_at,
    )


def _override_table_snapshot(conn) -> list[tuple]:
    return conn.execute(
        text(
            """
            SELECT employee_id, profile_override::text, updated_at::text
            FROM public.employee_import_profile_overrides
            ORDER BY employee_id
            """
        )
    ).fetchall()


@pytest.fixture
def preview_fixture(seed, tmp_path: Path):
    _require_phase_b4()
    suffix = uuid4().hex[:8]
    user_id = int(seed["initiator_user_id"])
    unit_id = int(seed["unit_id"])

    iin_new = f"{int(uuid4().int % 10**12):012d}"
    iin_identical = f"{int(uuid4().int % 10**12):012d}"
    iin_update = f"{int(uuid4().int % 10**12):012d}"
    iin_conflict = f"{int(uuid4().int % 10**12):012d}"
    iin_sections = f"{int(uuid4().int % 10**12):012d}"
    orphan_iin = f"{int(uuid4().int % 10**12):012d}"
    ambiguous_name = f"Дубликат Дубликат Дубликат {suffix}"

    employee_ids: dict[str, int | None] = {
        "new": None,
        "identical": None,
        "update": None,
        "conflict": None,
        "sections": None,
    }
    ambiguous_ids: list[int] = []

    try:
        with engine.begin() as conn:
            employee_ids["new"] = _create_employee(
                conn, full_name=f"Новый Сотрудник {suffix}", org_unit_id=unit_id
            )
            _attach_iin(conn, employee_id=employee_ids["new"], iin_value=iin_new, created_by=user_id)

            employee_ids["identical"] = _create_employee(
                conn, full_name=f"Идентичный Сотрудник {suffix}", org_unit_id=unit_id
            )
            _attach_iin(conn, employee_id=employee_ids["identical"], iin_value=iin_identical, created_by=user_id)
            upsert_employee_override(
                conn,
                employee_ids["identical"],
                profile={"notes": "same notes"},
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
                    "employee_id": employee_ids["identical"],
                    "updated_at": datetime(2026, 6, 9, 10, 0, tzinfo=timezone.utc),
                },
            )

            employee_ids["update"] = _create_employee(
                conn, full_name=f"Обновляемый Сотрудник {suffix}", org_unit_id=unit_id
            )
            _attach_iin(conn, employee_id=employee_ids["update"], iin_value=iin_update, created_by=user_id)
            upsert_employee_override(
                conn,
                employee_ids["update"],
                profile={"training": [{"topic": "old target training"}]},
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
                    "employee_id": employee_ids["update"],
                    "updated_at": datetime(2026, 6, 8, 10, 0, tzinfo=timezone.utc),
                },
            )

            employee_ids["conflict"] = _create_employee(
                conn, full_name=f"Конфликтный Сотрудник {suffix}", org_unit_id=unit_id
            )
            _attach_iin(conn, employee_id=employee_ids["conflict"], iin_value=iin_conflict, created_by=user_id)
            upsert_employee_override(
                conn,
                employee_ids["conflict"],
                profile={"notes": "newer target notes"},
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
                    "employee_id": employee_ids["conflict"],
                    "updated_at": datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc),
                },
            )

            employee_ids["sections"] = _create_employee(
                conn, full_name=f"Секции Сотрудник {suffix}", org_unit_id=unit_id
            )
            _attach_iin(conn, employee_id=employee_ids["sections"], iin_value=iin_sections, created_by=user_id)
            upsert_employee_override(
                conn,
                employee_ids["sections"],
                profile={
                    "certificates": [{"kind": "A", "topic": "old", "date": "2020-01-01"}],
                    "training": [{"topic": "old training", "date": "2020-02-01"}],
                },
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
                    "employee_id": employee_ids["sections"],
                    "updated_at": datetime(2026, 6, 8, 10, 0, tzinfo=timezone.utc),
                },
            )

            ambiguous_ids = [
                _create_employee(conn, full_name=ambiguous_name, org_unit_id=unit_id),
                _create_employee(conn, full_name=ambiguous_name, org_unit_id=unit_id),
            ]

        keys = {
            "new": f"iin:{iin_new}",
            "identical": f"iin:{iin_identical}",
            "update": f"iin:{iin_update}",
            "conflict": f"iin:{iin_conflict}",
            "sections": f"iin:{iin_sections}",
            "orphan": f"iin:{orphan_iin}",
            "ambiguous": build_employee_key(full_name=ambiguous_name),
        }
        employees = [
            _employee_record(
                employee_key=keys["new"],
                full_name=f"Новый Сотрудник {suffix}",
                source_id=employee_ids["new"],
                iin=iin_new,
            ),
            _employee_record(
                employee_key=keys["identical"],
                full_name=f"Идентичный Сотрудник {suffix}",
                source_id=employee_ids["identical"],
                iin=iin_identical,
            ),
            _employee_record(
                employee_key=keys["update"],
                full_name=f"Обновляемый Сотрудник {suffix}",
                source_id=employee_ids["update"],
                iin=iin_update,
            ),
            _employee_record(
                employee_key=keys["conflict"],
                full_name=f"Конфликтный Сотрудник {suffix}",
                source_id=employee_ids["conflict"],
                iin=iin_conflict,
            ),
            _employee_record(
                employee_key=keys["sections"],
                full_name=f"Секции Сотрудник {suffix}",
                source_id=employee_ids["sections"],
                iin=iin_sections,
            ),
            _employee_record(
                employee_key=keys["orphan"],
                full_name="Orphan",
                source_id=999,
                iin=orphan_iin,
            ),
            _employee_record(
                employee_key=keys["ambiguous"],
                full_name=ambiguous_name,
                source_id=999,
            ),
        ]
        overrides = [
            _override_record(employee_key=keys["new"], profile_override={"notes": "brand new"}),
            _override_record(employee_key=keys["identical"], profile_override={"notes": "same notes"}),
            _override_record(
                employee_key=keys["update"],
                profile_override={"notes": "incoming update"},
                updated_at="2026-06-10T10:00:00+00:00",
            ),
            _override_record(
                employee_key=keys["conflict"],
                profile_override={"notes": "incoming conflict"},
                updated_at="2026-06-10T10:00:00+00:00",
            ),
            _override_record(
                employee_key=keys["sections"],
                profile_override={
                    "certificates": [{"kind": "B", "topic": "new", "date": "2021-01-01"}],
                    "notes": "new note",
                },
            ),
            _override_record(employee_key=keys["orphan"], profile_override={"notes": "orphan"}),
            _override_record(employee_key=keys["ambiguous"], profile_override={"notes": "ambiguous"}),
        ]
        package_path = _write_package(tmp_path, employees=employees, overrides=overrides)

        yield {
            "package_path": package_path,
            "keys": keys,
            "employee_ids": employee_ids,
            "ambiguous_ids": ambiguous_ids,
        }
    finally:
        with engine.begin() as conn:
            for employee_id in [*employee_ids.values(), *ambiguous_ids]:
                if employee_id:
                    conn.execute(
                        text(
                            "DELETE FROM public.employee_import_profile_overrides WHERE employee_id = :id"
                        ),
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


def _item_by_key(result, employee_key: str):
    return next(item for item in result.items if item.employee_key == employee_key)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_preview_valid_package(preview_fixture) -> None:
    with engine.connect() as conn:
        result = preview_hr_sync_package(conn, package_path=preview_fixture["package_path"])

    assert result.validation_ok is True
    assert result.total_records == 7
    assert result.new_count == 1
    assert result.update_count == 0
    assert result.merge_count == 1
    assert result.identical_count == 1
    assert result.conflict_count == 2
    assert result.orphan_count == 1
    assert result.ambiguous_count == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_new_override_classified_as_insert(preview_fixture) -> None:
    with engine.connect() as conn:
        result = preview_hr_sync_package(conn, package_path=preview_fixture["package_path"])
    item = _item_by_key(result, preview_fixture["keys"]["new"])
    assert item.status == "new"
    assert item.action == "insert"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_identical_override_classified_as_skip(preview_fixture) -> None:
    with engine.connect() as conn:
        result = preview_hr_sync_package(conn, package_path=preview_fixture["package_path"])
    item = _item_by_key(result, preview_fixture["keys"]["identical"])
    assert item.status == "identical"
    assert item.action == "skip"
    assert item.changed_sections == []


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_changed_override_classified_as_merge(preview_fixture) -> None:
    with engine.connect() as conn:
        result = preview_hr_sync_package(conn, package_path=preview_fixture["package_path"])
    item = _item_by_key(result, preview_fixture["keys"]["update"])
    assert item.status == "merge"
    assert item.action == "update"
    assert "notes" in item.changed_sections


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_target_newer_classified_as_conflict(preview_fixture) -> None:
    with engine.connect() as conn:
        result = preview_hr_sync_package(conn, package_path=preview_fixture["package_path"])
    item = _item_by_key(result, preview_fixture["keys"]["conflict"])
    assert item.status == "conflict"
    assert item.action == "review_required"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_orphan_classified_as_skip(preview_fixture) -> None:
    with engine.connect() as conn:
        result = preview_hr_sync_package(conn, package_path=preview_fixture["package_path"])
    item = _item_by_key(result, preview_fixture["keys"]["orphan"])
    assert item.status == "orphan"
    assert item.action == "skip"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_ambiguous_classified_as_skip(preview_fixture) -> None:
    with engine.connect() as conn:
        result = preview_hr_sync_package(conn, package_path=preview_fixture["package_path"])
    item = _item_by_key(result, preview_fixture["keys"]["ambiguous"])
    assert item.status == "ambiguous"
    assert item.action == "skip"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_changed_sections_detects_certificates_training_notes(preview_fixture) -> None:
    with engine.connect() as conn:
        result = preview_hr_sync_package(conn, package_path=preview_fixture["package_path"])
    item = _item_by_key(result, preview_fixture["keys"]["sections"])
    assert item.status == "conflict"
    assert item.conflict_type == CONFLICT_TYPE_SECTION_OVERLAP
    assert "certificates" in item.changed_sections
    assert "notes" in item.changed_sections
    assert "training" in item.changed_sections


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_preview_does_not_modify_db(preview_fixture) -> None:
    with engine.connect() as conn:
        before = _override_table_snapshot(conn)
        preview_hr_sync_package(conn, package_path=preview_fixture["package_path"])
        after = _override_table_snapshot(conn)
    assert before == after


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_invalid_package_rejected(preview_fixture, tmp_path: Path) -> None:
    broken_path = tmp_path / "broken_preview.zip"
    with zipfile.ZipFile(preview_fixture["package_path"], "r") as src, zipfile.ZipFile(broken_path, "w") as dst:
        for item in src.infolist():
            if item.filename != "metadata.json":
                dst.writestr(item, src.read(item.filename))

    with engine.connect() as conn:
        result = preview_hr_sync_package(conn, package_path=broken_path)

    assert result.validation_ok is False
    assert result.total_records == 0
    assert any("preview aborted" in error for error in result.errors)
