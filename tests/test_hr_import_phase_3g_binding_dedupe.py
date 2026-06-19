"""Tests for ADR-039/040 — normalized record binding dedupe and IIN search."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.hr_import_employee_binding_service import (
    propagate_employee_id_to_normalized_records,
    repair_batch_employee_bindings,
)
from app.services.hr_import_normalized_record_service import list_review_normalized_records
from app.services.hr_import_service import import_control_list
from tests.test_employee_documents_routes import _phase_1a_available
from tests.test_hr_import_phase_3d_normalized_records_review_api import (
    _build_doctors_sheet_with_column_m,
)
from tests.test_hr_import_phase_3g_employee_binding import (
    _create_employee_with_iin,
    _delete_batch,
    _import_batch,
    _require_phase_3g,
    _test_iin,
)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    from tests.conftest import auth_headers

    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def client():
    return TestClient(app)


def _import_batch_with_records(
    tmp_path: Path,
    seed,
    *,
    full_name: str,
    iin: str,
) -> int:
    source = tmp_path / f"binding_dedupe_{uuid4().hex[:8]}.xlsx"
    _build_doctors_sheet_with_column_m(
        source,
        "КазНМУ, 1982; ПК 144 ч",
        "сертификат специалиста, действ. до 01.01.2028",
    )
    with engine.begin() as conn:
        batch_id, _, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
    with engine.begin() as conn:
        _set_row_identity(conn, int(batch_id), full_name=full_name, iin=iin, all_rows=True)
    return int(batch_id)


def _set_row_identity(
    conn,
    batch_id: int,
    *,
    full_name: str,
    iin: str,
    all_rows: bool = False,
) -> None:
    import json

    limit_sql = "" if all_rows else "LIMIT 1"
    rows = conn.execute(
        text(
            f"""
            SELECT row_id, normalized_payload
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
            ORDER BY row_id
            {limit_sql}
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()
    for row in rows:
        payload = dict(row["normalized_payload"] or {})
        payload["full_name"] = full_name
        payload["iin"] = iin
        conn.execute(
            text(
                """
                UPDATE public.hr_import_rows
                SET normalized_payload = CAST(:payload AS jsonb)
                WHERE row_id = :row_id
                """
            ),
            {"row_id": int(row["row_id"]), "payload": json.dumps(payload, ensure_ascii=False)},
        )


def _cleanup_employee(conn, employee_id: int | None) -> None:
    if employee_id is None:
        return
    conn.execute(text("DELETE FROM public.employee_identities WHERE employee_id = :id"), {"id": employee_id})
    conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": employee_id})


def _insert_education_record(
    conn,
    *,
    batch_id: int,
    row_id: int,
    source_record_key: str,
) -> int:
    doc_type_id = conn.execute(
        text("SELECT document_type_id FROM public.document_types WHERE code = 'EDUCATION_GRADUATION' LIMIT 1")
    ).scalar_one()
    return int(
        conn.execute(
            text(
                """
                INSERT INTO public.hr_import_normalized_records (
                    batch_id, row_id, employee_id, fragment_index, source_field, source_text,
                    source_record_key, record_kind, document_type_id, document_type_code,
                    title, provider, issue_date, parse_method, review_status
                )
                VALUES (
                    :batch_id, :row_id, NULL, 0, 'education_raw', 'КазНМУ',
                    :source_record_key, 'education', :document_type_id, 'EDUCATION_GRADUATION',
                    'КазНМУ', 'КазНМУ', DATE '1982-01-01', 'manual', 'approved'
                )
                RETURNING normalized_record_id
                """
            ),
            {
                "batch_id": batch_id,
                "row_id": row_id,
                "source_record_key": source_record_key,
                "document_type_id": int(doc_type_id),
            },
        ).scalar_one()
    )


def _second_row_id(conn, batch_id: int, *, full_name: str, iin: str) -> int:
    import json

    source_row = conn.execute(
        text(
            """
            SELECT source_sheet, source_row_number, raw_payload, normalized_payload, match_status
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
            ORDER BY row_id
            LIMIT 1
            """
        ),
        {"batch_id": batch_id},
    ).mappings().first()
    payload = dict(source_row["normalized_payload"] or {})
    payload["full_name"] = full_name
    payload["iin"] = iin
    return int(
        conn.execute(
            text(
                """
                INSERT INTO public.hr_import_rows (
                    batch_id, source_sheet, source_row_number, raw_payload, normalized_payload, match_status
                )
                VALUES (
                    :batch_id, :source_sheet, :source_row_number, :raw_payload,
                    CAST(:payload AS jsonb), :match_status
                )
                RETURNING row_id
                """
            ),
            {
                "batch_id": batch_id,
                "source_sheet": source_row["source_sheet"],
                "source_row_number": int(source_row["source_row_number"]) + 9000,
                "raw_payload": json.dumps(source_row["raw_payload"] or {}),
                "payload": json.dumps(payload),
                "match_status": source_row["match_status"],
            },
        ).scalar_one()
    )


def test_propagate_duplicate_source_record_key_does_not_raise_integrity_error(seed, tmp_path: Path) -> None:
    _require_phase_3g()
    if not _phase_1a_available():
        pytest.skip("employees tables missing")

    suffix = uuid4().hex[:8]
    iin = _test_iin(f"8{suffix}")
    full_name = f"DupBind {suffix}"
    batch_id = None
    emp_id = None

    try:
        batch_id = _import_batch(tmp_path, seed, full_name=full_name, iin=iin)
        with engine.begin() as conn:
            emp_id = _create_employee_with_iin(
                conn,
                full_name=full_name,
                iin=iin,
                org_unit_id=int(seed["unit_id"]),
                created_by=int(seed["initiator_user_id"]),
            )
            row_id = conn.execute(
                text(
                    """
                    SELECT row_id FROM public.hr_import_rows
                    WHERE batch_id = :batch_id ORDER BY row_id LIMIT 1
                    """
                ),
                {"batch_id": batch_id},
            ).scalar_one()
            row_id_2 = _second_row_id(conn, batch_id, full_name=full_name, iin=iin)
            record_a = _insert_education_record(
                conn,
                batch_id=batch_id,
                row_id=int(row_id),
                source_record_key=f"pytest-dup-a-{uuid4().hex}",
            )
            record_b = _insert_education_record(
                conn,
                batch_id=batch_id,
                row_id=int(row_id_2),
                source_record_key=f"pytest-dup-b-{uuid4().hex}",
            )
            stats_a = propagate_employee_id_to_normalized_records(conn, int(row_id), emp_id)
            stats_b = propagate_employee_id_to_normalized_records(conn, int(row_id_2), emp_id)
            statuses = conn.execute(
                text(
                    """
                    SELECT normalized_record_id, review_status, employee_id
                    FROM public.hr_import_normalized_records
                    WHERE normalized_record_id IN (:a, :b)
                    ORDER BY normalized_record_id
                    """
                ),
                {"a": record_a, "b": record_b},
            ).mappings().all()
        assert stats_a["updated"] + stats_a["superseded"] >= 1
        assert stats_b["updated"] + stats_b["superseded"] >= 1
        bound_rows = [row for row in statuses if row["employee_id"] == emp_id]
        superseded_rows = [row for row in statuses if row["review_status"] == "superseded"]
        assert len(bound_rows) >= 1
        assert len(superseded_rows) >= 1
    finally:
        if batch_id is not None:
            with engine.begin() as conn:
                _cleanup_employee(conn, emp_id)
                _delete_batch(conn, batch_id)


def test_repair_bindings_handles_existing_open_record(seed, tmp_path: Path) -> None:
    _require_phase_3g()
    if not _phase_1a_available():
        pytest.skip("employees tables missing")

    suffix = uuid4().hex[:8]
    iin = _test_iin(f"7{suffix}")
    full_name = f"RepairBind {suffix}"
    batch_id = None
    emp_id = None

    try:
        batch_id = _import_batch(tmp_path, seed, full_name=full_name, iin=iin)
        with engine.begin() as conn:
            emp_id = _create_employee_with_iin(
                conn,
                full_name=full_name,
                iin=iin,
                org_unit_id=int(seed["unit_id"]),
                created_by=int(seed["initiator_user_id"]),
            )
            row_id = conn.execute(
                text(
                    """
                    SELECT row_id FROM public.hr_import_rows
                    WHERE batch_id = :batch_id ORDER BY row_id LIMIT 1
                    """
                ),
                {"batch_id": batch_id},
            ).scalar_one()
            row_id_2 = _second_row_id(conn, batch_id, full_name=full_name, iin=iin)
            record_a = _insert_education_record(
                conn,
                batch_id=batch_id,
                row_id=int(row_id),
                source_record_key=f"pytest-repair-a-{uuid4().hex}",
            )
            record_b = _insert_education_record(
                conn,
                batch_id=batch_id,
                row_id=int(row_id_2),
                source_record_key=f"pytest-repair-b-{uuid4().hex}",
            )
            propagate_employee_id_to_normalized_records(conn, int(row_id), emp_id)
            conn.execute(
                text(
                    """
                    UPDATE public.hr_import_rows
                    SET employee_id = :employee_id
                    WHERE row_id = :row_id
                    """
                ),
                {"employee_id": emp_id, "row_id": row_id},
            )
            summary = repair_batch_employee_bindings(conn, batch_id)
            assert summary["rows_processed"] >= 1
            assert summary.get("normalized_records_superseded", 0) >= 0
            still_open = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.hr_import_normalized_records
                    WHERE normalized_record_id IN (:a, :b)
                      AND review_status IN ('pending', 'approved')
                      AND employee_id = :employee_id
                    """
                ),
                {"a": record_a, "b": record_b, "employee_id": emp_id},
            ).scalar_one()
            assert int(still_open) <= 1
    finally:
        if batch_id is not None:
            with engine.begin() as conn:
                _cleanup_employee(conn, emp_id)
                _delete_batch(conn, batch_id)


def test_search_normalized_records_by_iin(seed, tmp_path: Path) -> None:
    _require_phase_3g()

    suffix = uuid4().hex[:8]
    iin = _test_iin(f"6{suffix}")
    full_name_kaz = f"Әбітаев Ерхан {suffix}"
    batch_id = None

    try:
        batch_id = _import_batch_with_records(
            tmp_path, seed, full_name=full_name_kaz, iin=iin
        )
        with engine.begin() as conn:
            all_records = list_review_normalized_records(conn, batch_id=batch_id)
            assert all_records["total"] >= 1
            by_iin = list_review_normalized_records(conn, batch_id=batch_id, q_iin=iin)
            by_wrong_name = list_review_normalized_records(conn, batch_id=batch_id, q_name="Әбитаев")
        assert by_iin["total"] >= 1
        assert by_wrong_name["total"] == 0
    finally:
        if batch_id is not None:
            with engine.begin() as conn:
                _delete_batch(conn, batch_id)


def test_api_search_normalized_records_by_iin(seed, tmp_path: Path, privileged_headers) -> None:
    _require_phase_3g()

    suffix = uuid4().hex[:8]
    iin = _test_iin(f"4{suffix}")
    full_name_kaz = f"Әбітаев Ерхан {suffix}"
    batch_id = None
    client = TestClient(app)

    try:
        batch_id = _import_batch_with_records(
            tmp_path, seed, full_name=full_name_kaz, iin=iin
        )
        res = client.get(
            "/directory/personnel/import/normalized-records",
            headers=privileged_headers,
            params={"batch_id": batch_id, "q_iin": iin},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["total"] >= 1

        wrong_name = client.get(
            "/directory/personnel/import/normalized-records",
            headers=privileged_headers,
            params={"batch_id": batch_id, "q_name": "Әбитаев"},
        )
        assert wrong_name.status_code == 200
        assert wrong_name.json()["total"] == 0
    finally:
        if batch_id is not None:
            with engine.begin() as conn:
                _delete_batch(conn, batch_id)


def test_bind_api_handles_duplicate_open_record(seed, tmp_path: Path, privileged_headers) -> None:
    _require_phase_3g()
    if not _phase_1a_available():
        pytest.skip("employees tables missing")

    suffix = uuid4().hex[:8]
    iin = _test_iin(f"5{suffix}")
    full_name = f"ApiBind {suffix}"
    batch_id = None
    emp_id = None
    client = TestClient(app)

    try:
        batch_id = _import_batch(tmp_path, seed, full_name=full_name, iin=iin)
        with engine.begin() as conn:
            emp_id = _create_employee_with_iin(
                conn,
                full_name=full_name,
                iin=iin,
                org_unit_id=int(seed["unit_id"]),
                created_by=int(seed["initiator_user_id"]),
            )
            row_id = conn.execute(
                text(
                    """
                    SELECT row_id FROM public.hr_import_rows
                    WHERE batch_id = :batch_id ORDER BY row_id LIMIT 1
                    """
                ),
                {"batch_id": batch_id},
            ).scalar_one()
            row_id_2 = _second_row_id(conn, batch_id, full_name=full_name, iin=iin)
            record_a = _insert_education_record(
                conn,
                batch_id=batch_id,
                row_id=int(row_id),
                source_record_key=f"pytest-api-a-{uuid4().hex}",
            )
            record_b = _insert_education_record(
                conn,
                batch_id=batch_id,
                row_id=int(row_id_2),
                source_record_key=f"pytest-api-b-{uuid4().hex}",
            )
            propagate_employee_id_to_normalized_records(conn, int(row_id), emp_id)

        res = client.patch(
            f"/directory/personnel/import/normalized-records/{record_b}",
            headers=privileged_headers,
            json={"employee_id": emp_id},
        )
        assert res.status_code == 200
        assert "IntegrityError" not in res.text
        assert "uq_hinr_employee_source_key_open" not in res.text
    finally:
        if batch_id is not None:
            with engine.begin() as conn:
                _cleanup_employee(conn, emp_id)
                _delete_batch(conn, batch_id)
