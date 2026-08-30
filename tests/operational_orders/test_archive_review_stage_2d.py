"""PostgreSQL API/service coverage for WP-PO-002 Stage 2D."""
from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Iterator

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.operational_orders.errors import OperationalOrderArchiveReviewConflictError
from app.operational_orders import auth_projection
from app.operational_orders.services import archive_review_service
from tests.conftest import auth_headers
from tests.operational_orders.conftest import _grant_user_permission, revoke_user_permission

pytestmark = pytest.mark.usefixtures("_require_oo_schema_fixture")

BASE = "/api/operational-orders/archive-review/rows"
PERMISSION = "OPERATIONAL_ORDER_ARCHIVE_REVIEW"


@pytest.fixture
def stage2d_row(seed) -> Iterator[int]:
    actor = int(seed["initiator_user_id"])
    fingerprint = hashlib.sha256(f"stage2d-{uuid.uuid4()}".encode()).hexdigest()
    with engine.begin() as conn:
        batch_id = int(
            conn.execute(
                text(
                    """
                    INSERT INTO operational_order_import_batches (
                        source_manifest_name, source_manifest_sha256, batch_fingerprint,
                        format_version, source_root_name, sheet_name, status,
                        total_rows, valid_rows, error_rows, file_count,
                        archive_section_count, created_by_user_id
                    ) VALUES (
                        'stage2d.xlsx', :sha, :fingerprint, 'v1', 'archive', 'orders',
                        'IMPORTED', 1, 1, 0, 1, 1, :actor
                    ) RETURNING id
                    """
                ),
                {"sha": hashlib.sha256(b"manifest").hexdigest(), "fingerprint": fingerprint, "actor": actor},
            ).scalar_one()
        )
        row_id = int(
            conn.execute(
                text(
                    """
                    INSERT INTO operational_order_import_rows (
                        batch_id, source_row_number, source_filename, source_document_type,
                        source_status, source_event_type, source_order_number, source_order_date,
                        source_folder, archive_section, relative_path, file_extension,
                        file_size, file_sha256, initial_review_state
                    ) VALUES (
                        :batch, '1', 'order.docx', 'Приказ', 'Найден', 'Исходный предмет',
                        '12-ө', DATE '2026-08-30', 'archive', 'Раздел А',
                        'Раздел А/order.docx', '.docx', 10, :sha, 'REQUISITES_PRECONFIRMED'
                    ) RETURNING id
                    """
                ),
                {"batch": batch_id, "sha": hashlib.sha256(b"file").hexdigest()},
            ).scalar_one()
        )
    try:
        yield row_id
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM operational_order_import_batches WHERE id=:id"), {"id": batch_id})


@pytest.fixture
def review_headers(seed):
    user_id = int(seed["executor_user_id"])
    with engine.begin() as conn:
        _grant_user_permission(conn, user_id, PERMISSION)
    try:
        yield auth_headers(user_id), user_id
    finally:
        with engine.begin() as conn:
            revoke_user_permission(conn, user_id, PERMISSION)


def confirmed_payload(version: int = 1) -> dict:
    return {
        "expected_version": version,
        "review_outcome": "CONFIRMED",
        "confirmed_document_type": " Приказ ",
        "confirmed_order_number": " 12-ө ",
        "confirmed_order_date": "2026-08-30",
        "confirmed_subject": " Подтверждённый предмет ",
        "review_comment": None,
    }


def test_detail_allowed_and_safe(client, oo_intake_headers, stage2d_row):
    response = client.get(f"{BASE}/{stage2d_row}", headers=oo_intake_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["row_id"] == stage2d_row
    assert body["source_document_type"] == "Приказ"
    assert body["relative_path"] == "Раздел А/order.docx"
    assert body["official_document_id"] is None
    assert body["version"] == 1
    serialized = response.text.lower()
    assert "file_sha256" not in serialized
    assert "postgresql" not in serialized
    assert ":\\" not in serialized


def test_hr_head_read_only_can_view_but_cannot_save(client, seed, stage2d_row):
    user_id = int(seed["executor_user_id"])
    with engine.begin() as conn:
        original_role_id = int(conn.execute(text("SELECT role_id FROM users WHERE user_id=:id"), {"id": user_id}).scalar_one())
        hr_head_role_id = int(conn.execute(text("SELECT role_id FROM roles WHERE code='HR_HEAD'")).scalar_one())
        conn.execute(text("UPDATE users SET role_id=:role WHERE user_id=:id"), {"role": hr_head_role_id, "id": user_id})
        _grant_user_permission(conn, user_id, "OPERATIONAL_ORDERS_INTAKE_READ")
        revoke_user_permission(conn, user_id, PERMISSION)
    try:
        me_response = client.get("/auth/me", headers=auth_headers(user_id))
        assert me_response.status_code == 200, me_response.text
        assert me_response.json()["role_code"] == "HR_HEAD"
        assert me_response.json()["operational_orders_permissions"]["archive_review"] is False
        assert me_response.json()["has_operational_order_archive_review"] is False
        assert client.get(f"{BASE}/{stage2d_row}", headers=auth_headers(user_id)).status_code == 200
        response = client.patch(f"{BASE}/{stage2d_row}", json=confirmed_payload(), headers=auth_headers(user_id))
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "OO_FORBIDDEN"
    finally:
        with engine.begin() as conn:
            revoke_user_permission(conn, user_id, "OPERATIONAL_ORDERS_INTAKE_READ")
            conn.execute(text("UPDATE users SET role_id=:role WHERE user_id=:id"), {"role": original_role_id, "id": user_id})


def test_detail_without_read_or_review_permission_is_forbidden(client, seed, stage2d_row):
    user_id = int(seed["executor_user_id"])
    with engine.begin() as conn:
        revoke_user_permission(conn, user_id, "OPERATIONAL_ORDERS_INTAKE_READ")
        revoke_user_permission(conn, user_id, PERMISSION)
    response = client.get(f"{BASE}/{stage2d_row}", headers=auth_headers(user_id))
    assert response.status_code == 403
    assert response.json()["detail"] == {"code": "OO_FORBIDDEN", "message": "Access denied."}


@pytest.mark.parametrize("role_code", ["HR_reg", "ADMIN"])
def test_role_grants_allow_review(client, seed, stage2d_row, role_code):
    user_id = int(seed["executor_user_id"])
    with engine.begin() as conn:
        original_role_id = int(conn.execute(text("SELECT role_id FROM users WHERE user_id=:id"), {"id": user_id}).scalar_one())
        target_role_id = int(conn.execute(text("SELECT role_id FROM roles WHERE code=:code"), {"code": role_code}).scalar_one())
        revoke_user_permission(conn, user_id, PERMISSION)
        conn.execute(text("UPDATE users SET role_id=:role WHERE user_id=:id"), {"role": target_role_id, "id": user_id})
    try:
        me_response = client.get("/auth/me", headers=auth_headers(user_id))
        assert me_response.status_code == 200, me_response.text
        me_body = me_response.json()
        assert me_body["full_name"] == "Pytest Executor"
        assert me_body["has_operational_order_archive_review"] is True
        assert me_body["operational_orders_permissions"]["archive_review"] is True
        if role_code == "HR_reg":
            assert me_body["has_operational_orders_read"] is False
            assert client.get("/api/operational-orders/draft-workspaces", headers=auth_headers(user_id)).status_code == 403
            assert client.get("/api/operational-orders/documents", headers=auth_headers(user_id)).status_code == 403
        response = client.patch(f"{BASE}/{stage2d_row}", json=confirmed_payload(), headers=auth_headers(user_id))
        assert response.status_code == 200, response.text
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE users SET role_id=:role WHERE user_id=:id"), {"role": original_role_id, "id": user_id})


@pytest.mark.parametrize(
    "outcome",
    [
        "CONFIRMED",
        "NEEDS_CLARIFICATION",
        "DRAFT_ORDER",
        "ORDER_ANNEX",
        "SUPPORTING_DOCUMENT",
        "DUPLICATE",
        "NOT_AN_ORDER",
    ],
)
def test_save_each_outcome_and_server_side_actor(client, review_headers, stage2d_row, outcome):
    headers, actor_id = review_headers
    payload = confirmed_payload()
    payload["review_outcome"] = outcome
    if outcome != "CONFIRMED":
        payload["review_comment"] = f"Причина: {outcome}"
    response = client.patch(f"{BASE}/{stage2d_row}", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["review_outcome"] == outcome
    assert body["reviewer_display_name"] == "Pytest Executor"
    assert body["reviewed_at"] is not None
    assert "reviewed_by_user_id" not in body
    assert "email" not in response.text.lower()
    assert body["version"] == 2
    if outcome == "CONFIRMED":
        assert body["confirmed_order_number"] == "12-ө"
    else:
        assert body["confirmed_document_type"] is None
        assert body["confirmed_order_number"] is None
        assert body["confirmed_order_date"] is None
        assert body["confirmed_subject"] is None
    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT reviewed_by_user_id FROM operational_order_import_rows WHERE id=:id"),
            {"id": stage2d_row},
        ).scalar_one() == actor_id


def test_non_confirmed_outcome_clears_supplied_confirmed_fields(client, review_headers, stage2d_row):
    payload = confirmed_payload()
    payload.update(review_outcome="DUPLICATE", review_comment="Дубль")
    response = client.patch(f"{BASE}/{stage2d_row}", json=payload, headers=review_headers[0])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["review_outcome"] == "DUPLICATE"
    assert body["confirmed_document_type"] is None
    assert body["confirmed_order_number"] is None
    assert body["confirmed_order_date"] is None
    assert body["confirmed_subject"] is None


def test_reviewer_display_falls_back_to_login(client, review_headers, stage2d_row):
    actor_id = review_headers[1]
    with engine.begin() as conn:
        original_name, login = conn.execute(
            text("SELECT full_name, login FROM users WHERE user_id=:id"), {"id": actor_id}
        ).one()
        conn.execute(text("UPDATE users SET full_name=' ' WHERE user_id=:id"), {"id": actor_id})
    try:
        response = client.patch(
            f"{BASE}/{stage2d_row}",
            json={"expected_version": 1, "review_outcome": "DUPLICATE", "review_comment": "Дубль"},
            headers=review_headers[0],
        )
        assert response.status_code == 200, response.text
        assert response.json()["reviewer_display_name"] == login
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE users SET full_name=:name WHERE user_id=:id"), {"id": actor_id, "name": original_name})


def test_privileged_projection_does_not_invent_archive_review_permission(monkeypatch):
    monkeypatch.setattr(auth_projection, "is_privileged", lambda _user: True)
    monkeypatch.setattr(auth_projection, "has_admin_permission", lambda _uid, _code: False)
    permissions = auth_projection.build_operational_orders_permissions({"user_id": 999, "role_id": 999})
    assert permissions["intake_read"] is True
    assert permissions["archive_review"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {**confirmed_payload(), "confirmed_order_number": ""},
        {"expected_version": 1, "review_outcome": "DUPLICATE", "review_comment": ""},
        {**confirmed_payload(), "official_document_id": 99},
        {**confirmed_payload(), "source_order_number": "changed"},
        {**confirmed_payload(), "actor_user_id": 999},
        {**confirmed_payload(), "reviewed_by_user_id": 999},
    ],
)
def test_validation_and_forbidden_fields(client, review_headers, stage2d_row, payload):
    response = client.patch(f"{BASE}/{stage2d_row}", json=payload, headers=review_headers[0])
    assert response.status_code == 422
    with engine.connect() as conn:
        row = conn.execute(text("SELECT review_outcome, source_order_number, official_document_id, version FROM operational_order_import_rows WHERE id=:id"), {"id": stage2d_row}).one()
    assert tuple(row) == (None, "12-ө", None, 1)


def test_optimistic_lock_and_completed_transition(client, review_headers, stage2d_row):
    first = client.patch(f"{BASE}/{stage2d_row}", json=confirmed_payload(), headers=review_headers[0])
    assert first.status_code == 200
    stale = client.patch(f"{BASE}/{stage2d_row}", json=confirmed_payload(), headers=review_headers[0])
    assert stale.status_code == 409
    retry = client.patch(f"{BASE}/{stage2d_row}", json=confirmed_payload(2), headers=review_headers[0])
    assert retry.status_code == 409


def test_needs_clarification_can_transition_to_final(review_headers, stage2d_row):
    actor = review_headers[1]
    first = archive_review_service.save_archive_review(
        row_id=stage2d_row, actor_user_id=actor, expected_version=1,
        review_outcome="NEEDS_CLARIFICATION", review_comment="Уточнить",
    )
    assert first["version"] == 2
    final = archive_review_service.save_archive_review(
        row_id=stage2d_row, actor_user_id=actor, expected_version=2,
        review_outcome="DUPLICATE", review_comment="Дубль подтверждён",
    )
    assert final["review_outcome"] == "DUPLICATE"
    assert final["version"] == 3


@pytest.mark.parametrize(
    "outcome",
    ["CONFIRMED", "DRAFT_ORDER", "ORDER_ANNEX", "SUPPORTING_DOCUMENT", "DUPLICATE", "NOT_AN_ORDER"],
)
def test_needs_clarification_can_transition_to_each_terminal(review_headers, stage2d_row, outcome):
    actor = review_headers[1]
    archive_review_service.save_archive_review(
        row_id=stage2d_row,
        actor_user_id=actor,
        expected_version=1,
        review_outcome="NEEDS_CLARIFICATION",
        review_comment="Уточнить",
    )
    kwargs = confirmed_payload(version=2) if outcome == "CONFIRMED" else {
        "expected_version": 2,
        "review_outcome": outcome,
        "review_comment": f"Причина: {outcome}",
    }
    result = archive_review_service.save_archive_review(
        row_id=stage2d_row,
        actor_user_id=actor,
        **kwargs,
    )
    assert result["review_outcome"] == outcome


def test_optimistic_race_uses_independent_transactions(review_headers, stage2d_row):
    actor = review_headers[1]
    def update(outcome: str):
        try:
            return archive_review_service.save_archive_review(
                row_id=stage2d_row, actor_user_id=actor, expected_version=1,
                review_outcome=outcome, review_comment="Конкурирующая проверка",
            )["review_outcome"]
        except OperationalOrderArchiveReviewConflictError:
            return "CONFLICT"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["DUPLICATE", "NOT_AN_ORDER"]))
    assert results.count("CONFLICT") == 1
    assert len(set(results).intersection({"DUPLICATE", "NOT_AN_ORDER"})) == 1


def test_error_after_update_rolls_back(monkeypatch, review_headers, stage2d_row):
    original = archive_review_service._fetch_archive_review_row
    calls = 0
    def fail_after_update(conn, *, row_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("forced persistence failure")
        return original(conn, row_id=row_id)
    monkeypatch.setattr(archive_review_service, "_fetch_archive_review_row", fail_after_update)
    with pytest.raises(RuntimeError, match="forced persistence failure"):
        archive_review_service.save_archive_review(
            row_id=stage2d_row, actor_user_id=review_headers[1], expected_version=1,
            review_outcome="DUPLICATE", review_comment="Дубль",
        )
    with engine.connect() as conn:
        assert tuple(conn.execute(text("SELECT review_outcome, version FROM operational_order_import_rows WHERE id=:id"), {"id": stage2d_row}).one()) == (None, 1)


def test_official_tables_unchanged(client, review_headers, stage2d_row):
    tables = ("operational_order_draft_workspaces", "operational_order_documents", "operational_order_document_versions", "operational_order_document_localizations")
    with engine.connect() as conn:
        before = {table: conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() for table in tables}
    assert client.patch(f"{BASE}/{stage2d_row}", json=confirmed_payload(), headers=review_headers[0]).status_code == 200
    with engine.connect() as conn:
        after = {table: conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() for table in tables}
    assert after == before
