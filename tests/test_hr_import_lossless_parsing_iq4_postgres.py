"""PostgreSQL coverage for IQ-4 lossless A:S staging parsing."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from openpyxl import Workbook
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.db.engine import engine as app_engine
from app.services.hr_import_control_list_storage import remove_stored_control_list_file
from app.services.hr_import_document_candidate_service import parse_and_persist_document_candidates
from app.services.hr_import_normalized_record_service import populate_normalized_records
from app.services.hr_import_service import import_control_list


def _apply_iq2(conn) -> None:
    spec = spec_from_file_location(
        "iq2_iq4_test",
        Path("alembic/versions/iq2a1b2c3d4_hr_import_identity_quality_foundation.py"),
    )
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(conn)):
        module.upgrade()


@pytest.fixture
def disposable_iq4_database():
    source = make_url(os.environ["TEST_DATABASE_URL"])
    if (
        source.drivername.split("+", 1)[0] != "postgresql"
        or (source.host or "").lower() not in {"127.0.0.1", "localhost", "::1"}
        or str(source.database) != "corpsite_test"
    ):
        raise RuntimeError("IQ-4 tests require corpsite_test only as a loopback clone template")

    target_name = f"corpsite_iq4_{uuid4().hex[:16]}_test"
    target = source.set(database=target_name)
    admin_engine = create_engine(
        source.set(database="postgres").render_as_string(hide_password=False),
        isolation_level="AUTOCOMMIT",
    )
    target_engine = create_engine(target.render_as_string(hide_password=False))
    storage_refs: list[str] = []
    try:
        app_engine.dispose()
        with admin_engine.connect() as admin:
            admin.execute(text(f'CREATE DATABASE "{target_name}" TEMPLATE "{source.database}"'))
        connection = target_engine.connect()
        transaction = connection.begin()
        if connection.execute(
            text("SELECT to_regclass('public.hr_import_identity_review_events')")
        ).scalar_one():
            connection.execute(text("DROP TABLE public.hr_import_identity_quality_states"))
            connection.execute(text("DROP TABLE public.hr_import_identity_review_events"))
            connection.execute(
                text("ALTER TABLE public.hr_import_rows DROP CONSTRAINT uq_hr_import_rows_batch_row")
            )
            connection.execute(
                text("ALTER TABLE public.employees DROP CONSTRAINT IF EXISTS uq_employees_employee_person")
            )
            connection.execute(
                text("DROP FUNCTION IF EXISTS public.prevent_hr_import_identity_review_event_mutation()")
            )
            connection.execute(
                text("DROP FUNCTION IF EXISTS public.assert_hr_import_iq_event_advances_state()")
            )
            connection.execute(
                text("DROP FUNCTION IF EXISTS public.assert_hr_import_iq_effective_event()")
            )
        _apply_iq2(connection)
        imported_by = int(
            connection.execute(text("SELECT user_id FROM users ORDER BY user_id LIMIT 1")).scalar_one()
        )
        yield connection, storage_refs, imported_by
    finally:
        if "transaction" in locals():
            transaction.rollback()
        if "connection" in locals():
            connection.close()
        for storage_ref in storage_refs:
            remove_stored_control_list_file(storage_ref)
        target_engine.dispose()
        with admin_engine.connect() as admin:
            admin.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=:name AND pid<>pg_backend_pid()"
                ),
                {"name": target_name},
            )
            admin.execute(text(f'DROP DATABASE IF EXISTS "{target_name}"'))
        admin_engine.dispose()


def _write_lossless_workbook(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "врачи"
    sheet.append(
        [
            "Отделение", "ФИО", "Год рождения", "ИИН", "пол", "Национальность",
            "ВУЗ, год окончания", "Специальность по диплому", "Занимаемая должность",
            "Должность", "Дата", "Категория должности", "Стаж работы",
            "Повышение квалификации", "Квалификационная категория", "Степень", "Награды",
            "Примечание (декрет, инвалид, пенсионер)", "Телефоны",
        ]
    )
    sheet.append(
        [
            "IQ4 отделение", "IQ4 Сотрудник", 1984, "840101300123", "муж", "национальность",
            "ВУЗ, 2006", "специальность", "занимаемая", "штатная", "2017-04-03",
            "должностная категория", "15 лет", "повышение", "квалификационная категория",
            "степень", "награда", "примечание", "70000000000",
        ]
    )
    workbook.save(path)
    workbook.close()


def test_iq4_full_a_to_s_payload_is_lossless_in_postgres(
    disposable_iq4_database, tmp_path: Path
) -> None:
    conn, storage_refs, imported_by = disposable_iq4_database
    path = tmp_path / "контрольный2606.xlsx"
    _write_lossless_workbook(path)

    batch_id, summary, warnings = import_control_list(conn, file_path=path, imported_by=imported_by)
    # This is the real import pipeline, including the deferred IQ-2 event/state
    # constraints created for the unmatched synthetic IIN.
    conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    storage_refs.append(
        str(
            conn.execute(
                text(
                    "SELECT sf.storage_ref FROM hr_import_batches b "
                    "JOIN hr_source_files sf ON sf.source_file_id=b.source_file_id "
                    "WHERE b.batch_id=:batch_id"
                ),
                {"batch_id": batch_id},
            ).scalar_one()
        )
    )
    staged = conn.execute(
            text("SELECT raw_payload, normalized_payload FROM hr_import_rows WHERE batch_id=:batch_id"),
            {"batch_id": batch_id},
        ).mappings().one()
    payload = dict(staged["normalized_payload"])
    raw_payload = dict(staged["raw_payload"])

    assert warnings == []
    assert summary["total_rows"] == 1
    for field in (
        "department", "full_name", "birth_year_raw", "iin", "sex", "nationality",
        "education_raw", "diploma_specialty_raw", "position_raw", "staff_position_raw",
        "position_date_raw", "job_category_raw", "experience_raw", "training_raw",
        "education_training_raw", "certification_raw", "qualification_category_raw",
        "degree_raw", "awards_raw", "note_raw", "phone_raw",
    ):
        assert payload[field] != ""
        assert raw_payload[field] == payload[field]
    assert payload["birth_date"] == ""
    assert payload["qualification_raw"] == payload["qualification_category_raw"]

    counts_before = tuple(
        int(
            conn.execute(
                text(f"SELECT COUNT(*) FROM public.{table_name} WHERE batch_id=:batch_id"),
                {"batch_id": batch_id},
            ).scalar_one()
        )
        for table_name in ("hr_import_document_candidates", "hr_import_normalized_records")
    )
    parse_and_persist_document_candidates(conn, batch_id)
    populate_normalized_records(conn, batch_id)
    counts_after = tuple(
        int(
            conn.execute(
                text(f"SELECT COUNT(*) FROM public.{table_name} WHERE batch_id=:batch_id"),
                {"batch_id": batch_id},
            ).scalar_one()
        )
        for table_name in ("hr_import_document_candidates", "hr_import_normalized_records")
    )
    assert counts_after == counts_before
