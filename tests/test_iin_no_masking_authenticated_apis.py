"""Regression: authenticated HR/personnel APIs must not return masked IIN."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.services.hr_import_normalized_record_service import normalized_records_available
from app.services.hr_import_service import import_control_list
from tests.conftest import auth_headers, table_exists
from tests.test_import_hr_control_list import _build_sample_workbook

FORBIDDEN_IIN_KEYS = frozenset({"iin_masked", "masked_iin"})
IIN_VALUE_KEYS = frozenset({"iin", "iin_value"})


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _phase_2b_available() -> bool:
    with engine.begin() as conn:
        return table_exists(conn, "hr_import_batches") and table_exists(conn, "hr_import_rows")


def _require_phase_2b() -> None:
    if not _phase_2b_available():
        pytest.skip("HR import staging tables missing — run alembic upgrade head")


def _delete_batch(conn, batch_id: int) -> None:
    conn.execute(
        text("DELETE FROM public.hr_import_batches WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    )


def assert_no_masked_iin_in_payload(obj: Any, *, path: str = "response") -> None:
    """Recursively reject masked-IIN keys and asterisk-masked iin values."""
    if isinstance(obj, dict):
        for forbidden in FORBIDDEN_IIN_KEYS:
            assert forbidden not in obj, f"{forbidden} found at {path}"
        for key, value in obj.items():
            child_path = f"{path}.{key}"
            if key in IIN_VALUE_KEYS and isinstance(value, str) and value and "****" in value:
                raise AssertionError(f"masked iin value at {child_path}: {value!r}")
            assert_no_masked_iin_in_payload(value, path=child_path)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            assert_no_masked_iin_in_payload(item, path=f"{path}[{index}]")


def test_assert_no_masked_iin_helper_rejects_masked_keys_and_values() -> None:
    with pytest.raises(AssertionError, match="iin_masked"):
        assert_no_masked_iin_in_payload({"iin_masked": "9001****23"})
    with pytest.raises(AssertionError, match="masked iin value"):
        assert_no_masked_iin_in_payload({"iin": "9001****23"})


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def staged_batch(seed, tmp_path: Path):
    _require_phase_2b()
    source = tmp_path / f"iin_regression_{uuid4().hex[:8]}.xlsx"
    _build_sample_workbook(source)
    with engine.begin() as conn:
        batch_id, _, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
    yield batch_id
    with engine.begin() as conn:
        _delete_batch(conn, batch_id)


def _assert_get_json(client: TestClient, url: str, headers: dict[str, str]) -> None:
    resp = client.get(url, headers=headers)
    assert resp.status_code == 200, resp.text
    assert_no_masked_iin_in_payload(resp.json(), path=url)


def _assert_post_json(client: TestClient, url: str, headers: dict[str, str], body: dict) -> None:
    resp = client.post(url, headers=headers, json=body)
    assert resp.status_code == 200, resp.text
    assert_no_masked_iin_in_payload(resp.json(), path=url)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_authenticated_hr_import_apis_do_not_return_masked_iin(
    client: TestClient,
    privileged_headers,
    staged_batch,
):
    batch_id = staged_batch
    with engine.connect() as conn:
        row_id = conn.execute(
            text(
                """
                SELECT row_id
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                ORDER BY row_id
                LIMIT 1
                """
            ),
            {"batch_id": batch_id},
        ).scalar_one()

    endpoints = [
        f"/directory/personnel/import/batches/{batch_id}/rows?limit=20",
        f"/directory/personnel/import/batches/{batch_id}/document-candidates?limit=20",
        f"/directory/personnel/import/batches/{batch_id}/rows/{row_id}/review",
        f"/directory/personnel/import/batches/{batch_id}/education-profiles?limit=20",
        "/directory/personnel/hr-change-events?limit=20",
    ]
    for url in endpoints:
        _assert_get_json(client, url, privileged_headers)

    _assert_post_json(
        client,
        f"/directory/personnel/import/batches/{batch_id}/roster-promotion",
        privileged_headers,
        {"dry_run": True},
    )

    with engine.connect() as conn:
        if normalized_records_available(conn):
            _assert_get_json(
                client,
                f"/directory/personnel/import/normalized-records?batch_id={batch_id}&limit=20",
                privileged_headers,
            )
