"""Read-only API coverage for WP-PO-002 Stage 2C."""
from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.operational_orders.services import archive_review_service
from tests.conftest import auth_headers

pytestmark = pytest.mark.usefixtures("_require_oo_schema_fixture")

BASE = "/api/operational-orders/archive-review"


@pytest.fixture
def archive_review_batch(seed) -> Iterator[int]:
    actor_user_id = int(seed["initiator_user_id"])
    fingerprint = hashlib.sha256(f"stage-2c-{uuid.uuid4()}".encode()).hexdigest()
    manifest_sha = hashlib.sha256(b"stage-2c-manifest").hexdigest()
    with engine.begin() as conn:
        batch_id = int(
            conn.execute(
                text(
                    """
                    INSERT INTO public.operational_order_import_batches (
                        source_manifest_name, source_manifest_sha256, batch_fingerprint,
                        format_version, source_root_name, sheet_name, status,
                        total_rows, valid_rows, error_rows, file_count,
                        archive_section_count, created_by_user_id, created_at
                    ) VALUES (
                        'stage-2c.xlsx', :manifest_sha, :fingerprint,
                        'WP-PO-002-STAGE-2A-V1', 'archive', 'Производственные приказы', 'IMPORTED',
                        4, 4, 0, 4, 2, :actor_user_id, clock_timestamp() + interval '1 hour'
                    )
                    RETURNING id
                    """
                ),
                {
                    "manifest_sha": manifest_sha,
                    "fingerprint": fingerprint,
                    "actor_user_id": actor_user_id,
                },
            ).scalar_one()
        )
        rows = (
            ("1", "Альфа.docx", "Найден", "Назначение директора", "101-ө", "2026-01-01", "Раздел А", "Раздел А\\Альфа.docx", ".docx", "REQUISITES_PRECONFIRMED", "same"),
            ("2", "Бета.docx", "Не найден", "Отпуск сотрудника", None, None, "Раздел А", "Раздел А\\Бета.docx", ".docx", "NEEDS_REQUISITES", "same"),
            ("3", "Гамма.doc", "Требует проверки", "Производственный вопрос", "298-ө", "2026-02-03", "Раздел Б", "Раздел Б\\Гамма.doc", ".doc", "NEEDS_DOCUMENT_TYPE", "gamma"),
            ("4", "Секрет.pdf", "Не является приказом", "Не приказ", None, None, "Раздел Б", "C:secret\\Секрет.pdf", ".pdf", "POSSIBLE_NON_ORDER", "secret"),
        )
        for source_number, filename, status, subject, number, order_date, section, path, extension, state, content in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO public.operational_order_import_rows (
                        batch_id, source_row_number, source_filename, source_document_type,
                        source_status, source_event_type, source_order_number, source_order_date,
                        source_note, source_folder, archive_section, relative_path,
                        file_extension, file_size, file_sha256, initial_review_state
                    ) VALUES (
                        :batch_id, :source_number, :filename, 'Приказ',
                        :status, :subject, :number, CAST(:order_date AS date),
                        NULL, 'archive', :section, :path,
                        :extension, 10, :sha256, :state
                    )
                    """
                ),
                {
                    "batch_id": batch_id,
                    "source_number": source_number,
                    "filename": filename,
                    "status": status,
                    "subject": subject,
                    "number": number,
                    "order_date": order_date,
                    "section": section,
                    "path": path,
                    "extension": extension,
                    "sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "state": state,
                },
            )
    try:
        yield batch_id
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.operational_order_import_batches WHERE id = :batch_id"),
                {"batch_id": batch_id},
            )


def test_archive_review_requires_authentication(client):
    response = client.get(BASE)
    assert response.status_code in {401, 403}


def test_archive_review_forbidden_without_operational_orders_read(client, seed):
    response = client.get(BASE, headers=auth_headers(seed["executor_user_id"]))
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "OO_FORBIDDEN"


def test_archive_review_summary_pagination_and_safe_paths(client, oo_intake_headers, archive_review_batch):
    response = client.get(BASE, params={"limit": 2, "offset": 0}, headers=oo_intake_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["batch"]["batch_id"] == archive_review_batch
    assert body["stats"] == {
        "initial_quality": {
            "total": 4,
            "preconfirmed": 1,
            "incomplete": 3,
            "state_counts": {
                "REQUISITES_PRECONFIRMED": 1,
                "NEEDS_REQUISITES": 1,
                "NEEDS_DOCUMENT_TYPE": 1,
                "POSSIBLE_NON_ORDER": 1,
            },
        },
        "work_queue": {
            "pending_review": 4,
            "needs_clarification": 0,
            "completed_review": 0,
            "outcome_counts": {
                "CONFIRMED": 0,
                "DRAFT_ORDER": 0,
                "DUPLICATE": 0,
                "NEEDS_CLARIFICATION": 0,
                "NOT_AN_ORDER": 0,
                "ORDER_ANNEX": 0,
                "SUPPORTING_DOCUMENT": 0,
            },
        },
        "archive_section_count": 2,
        "extension_counts": {".doc": 1, ".docx": 2, ".pdf": 1},
        "duplicate_sha_excel_rows": [2, 3],
        "repeated_298_excel_rows": [4],
    }
    assert body["sections"] == ["Раздел А", "Раздел Б"]
    assert body["total"] == 4
    assert body["limit"] == 2
    assert [item["excel_row"] for item in body["items"]] == [2, 3]

    second_page = client.get(BASE, params={"limit": 2, "offset": 2}, headers=oo_intake_headers).json()
    assert [item["excel_row"] for item in second_page["items"]] == [4, 5]
    assert second_page["items"][1]["relative_path"] == ""
    serialized = str(second_page)
    assert "C:secret" not in serialized
    assert "postgresql" not in serialized.lower()
    assert "file_sha256" not in serialized


@pytest.mark.parametrize(
    ("params", "expected_excel_rows"),
    [
        ({"search": "отпуск"}, [3]),
        ({"search": "Гамма.doc"}, [4]),
        ({"search": "298-ө"}, [4]),
        ({"search": "Раздел А\\Бета"}, [3]),
        ({"search": "%"}, []),
        ({"search": "_"}, []),
        ({"initial_review_state": "POSSIBLE_NON_ORDER"}, [5]),
        ({"review_outcome": "UNREVIEWED"}, [2, 3, 4, 5]),
        ({"archive_section": "Раздел Б"}, [4, 5]),
        ({"only_missing_requisites": True}, [3, 5]),
        ({"only_duplicate_sha": True}, [2, 3]),
        ({"only_order_298": True}, [4]),
    ],
)
def test_archive_review_filters(client, oo_intake_headers, archive_review_batch, params, expected_excel_rows):
    response = client.get(BASE, params=params, headers=oo_intake_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == len(expected_excel_rows)
    assert [item["excel_row"] for item in body["items"]] == expected_excel_rows


def test_initial_quality_and_work_queue_are_independent(client, oo_intake_headers, archive_review_batch, seed):
    reviewer_id = int(seed["executor_user_id"])
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE operational_order_import_rows
                SET review_outcome='CONFIRMED', confirmed_document_type='Приказ',
                    confirmed_order_number='101-ө', confirmed_order_date=DATE '2026-01-01',
                    confirmed_subject='Назначение директора', reviewed_by_user_id=:reviewer,
                    reviewed_at=clock_timestamp(), version=version+1
                WHERE batch_id=:batch AND source_row_number='1'
                """
            ),
            {"batch": archive_review_batch, "reviewer": reviewer_id},
        )
        conn.execute(
            text(
                """
                UPDATE operational_order_import_rows
                SET review_outcome='NEEDS_CLARIFICATION', review_comment='Уточнить дату',
                    reviewed_by_user_id=:reviewer, reviewed_at=clock_timestamp(), version=version+1
                WHERE batch_id=:batch AND source_row_number='2'
                """
            ),
            {"batch": archive_review_batch, "reviewer": reviewer_id},
        )

    body = client.get(BASE, headers=oo_intake_headers).json()
    assert body["stats"]["initial_quality"] == {
        "total": 4,
        "preconfirmed": 1,
        "incomplete": 3,
        "state_counts": {
            "REQUISITES_PRECONFIRMED": 1,
            "NEEDS_REQUISITES": 1,
            "NEEDS_DOCUMENT_TYPE": 1,
            "POSSIBLE_NON_ORDER": 1,
        },
    }
    queue = body["stats"]["work_queue"]
    assert queue["pending_review"] == 2
    assert queue["needs_clarification"] == 1
    assert queue["completed_review"] == 1
    assert queue["outcome_counts"]["CONFIRMED"] == 1
    assert queue["outcome_counts"]["NEEDS_CLARIFICATION"] == 1
    assert queue["pending_review"] + queue["needs_clarification"] + queue["completed_review"] == 4
    confirmed = next(item for item in body["items"] if item["review_outcome"] == "CONFIRMED")
    assert confirmed["reviewer_display_name"] == "Pytest Executor"
    assert confirmed["reviewed_at"] is not None
    assert "email" not in str(body).lower()
    assert "password" not in str(body).lower()

    assert [item["excel_row"] for item in client.get(BASE, params={"review_outcome": "UNREVIEWED"}, headers=oo_intake_headers).json()["items"]] == [4, 5]
    assert [item["excel_row"] for item in client.get(BASE, params={"review_outcome": "CONFIRMED"}, headers=oo_intake_headers).json()["items"]] == [2]
    assert [item["excel_row"] for item in client.get(BASE, params={"review_outcome": "NEEDS_CLARIFICATION"}, headers=oo_intake_headers).json()["items"]] == [3]


def test_archive_review_empty_state(client, oo_intake_headers, monkeypatch):
    monkeypatch.setattr(
        archive_review_service,
        "list_latest_archive_review",
        lambda **kwargs: {
            "batch": None,
            "stats": None,
            "sections": [],
            "items": [],
            "total": 0,
            "limit": kwargs["limit"],
            "offset": kwargs["offset"],
        },
    )
    response = client.get(BASE, headers=oo_intake_headers)
    assert response.status_code == 200
    assert response.json()["batch"] is None
    assert response.json()["items"] == []


def test_archive_review_rejects_unknown_outcome_filter(client, oo_intake_headers):
    response = client.get(BASE, params={"review_outcome": "UNKNOWN"}, headers=oo_intake_headers)
    assert response.status_code == 422
