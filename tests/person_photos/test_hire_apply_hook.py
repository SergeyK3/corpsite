"""Tests for WP-ADR061-001D HIRE apply photo hook."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.person_photos import (
    BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE,
    BLOCKER_CODE_PHOTO_CANONICALIZATION_FAILED,
    CANONICALIZATION_MODE_HIRE_APPLY,
)
from app.person_photos.application.hire_apply_hook import ensure_hire_photo_ready
from app.person_photos.domain.errors import HirePhotoNotReadyError
from app.person_photos.domain.models import RESULT_COMMITTED, RESULT_IDEMPOTENT_OK
from app.personnel_intake.infrastructure import photo_storage as intake_photo_storage
from tests.conftest import table_exists
from tests.person_photos.hire_apply_helpers import make_hire_test_jpeg
from tests.ppr.conftest import insert_person, ppr_db_available


def _require_schema() -> None:
    with engine.begin() as conn:
        required = (
            "person_photos",
            "person_photo_sources",
            "personnel_applications",
            "personnel_application_blockers",
            "personnel_intake_drafts",
        )
        if not all(table_exists(conn, name) for name in required):
            pytest.skip("WP-ADR061 schema missing — run: alembic upgrade head")


@pytest.fixture
def photo_env(monkeypatch, tmp_path):
    root = tmp_path / "photos"
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", str(root))
    intake_photo_storage.ensure_intake_photo_storage_root()
    return root


@pytest.fixture
def hire_seed(photo_env):
    _require_schema()
    with engine.begin() as conn:
        user_row = conn.execute(text("SELECT user_id FROM public.users LIMIT 1")).mappings().first()
        if user_row is None:
            pytest.skip("users table empty")
        user_id = int(user_row["user_id"])
        person_id = insert_person(conn, full_name=f"ADR061D {uuid4().hex[:8]}")
        app_row = conn.execute(
            text(
                """
                INSERT INTO public.personnel_applications (
                    person_id, application_received_at, vacancy_check_status,
                    registered_by_user_id, status
                ) VALUES (
                    :person_id, CURRENT_DATE, 'confirmed_visually', :user_id, 'registered'
                )
                RETURNING application_id
                """
            ),
            {"person_id": person_id, "user_id": user_id},
        ).mappings().one()
        link_row = conn.execute(
            text(
                """
                INSERT INTO public.personnel_intake_links (
                    application_id, token_hash, status, expires_at, issued_by_user_id
                ) VALUES (
                    :application_id, :token_hash, 'issued', NOW() + INTERVAL '7 days', :user_id
                )
                RETURNING link_id
                """
            ),
            {
                "application_id": int(app_row["application_id"]),
                "token_hash": uuid4().hex,
                "user_id": user_id,
            },
        ).mappings().one()
        conn.execute(
            text(
                """
                INSERT INTO public.personnel_intake_drafts (
                    application_id, link_id, status, payload
                ) VALUES (
                    :application_id, :link_id, 'editable', CAST(:payload AS jsonb)
                )
                """
            ),
            {
                "application_id": int(app_row["application_id"]),
                "link_id": int(link_row["link_id"]),
                "payload": '{"personal": {"photo_file_id": ""}}',
            },
        )
    return {
        "person_id": person_id,
        "application_id": int(app_row["application_id"]),
        "user_id": user_id,
    }


def _open_blocker_count(application_id: int, blocker_code: str) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.personnel_application_blockers
                    WHERE application_id = :application_id
                      AND blocker_code = :blocker_code
                      AND resolved_at IS NULL
                    """
                ),
                {"application_id": application_id, "blocker_code": blocker_code},
            ).scalar_one()
        )


def _set_draft_photo_file_id(application_id: int, file_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.personnel_intake_drafts
                SET payload = jsonb_set(
                    COALESCE(payload, '{}'::jsonb),
                    '{personal,photo_file_id}',
                    to_jsonb(CAST(:file_id AS text)),
                    true
                )
                WHERE application_id = :application_id
                """
            ),
            {"application_id": application_id, "file_id": file_id},
        )


def _save_intake_photo(application_id: int, file_id: str, content: bytes) -> None:
    intake_photo_storage.save_intake_photo(application_id, file_id, content)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_missing_photo_upserts_blocker_and_aborts(hire_seed) -> None:
    with pytest.raises(HirePhotoNotReadyError, match="unavailable"):
        ensure_hire_photo_ready(
            application_id=hire_seed["application_id"],
            person_id=hire_seed["person_id"],
            actor_user_id=hire_seed["user_id"],
        )
    assert _open_blocker_count(hire_seed["application_id"], BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_retry_after_open_blocker_with_valid_photo_succeeds(hire_seed) -> None:
    with pytest.raises(HirePhotoNotReadyError):
        ensure_hire_photo_ready(
            application_id=hire_seed["application_id"],
            person_id=hire_seed["person_id"],
            actor_user_id=hire_seed["user_id"],
        )
    assert _open_blocker_count(hire_seed["application_id"], BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE) == 1

    file_id = uuid4().hex
    _set_draft_photo_file_id(hire_seed["application_id"], file_id)
    _save_intake_photo(hire_seed["application_id"], file_id, make_hire_test_jpeg())

    result = ensure_hire_photo_ready(
        application_id=hire_seed["application_id"],
        person_id=hire_seed["person_id"],
        actor_user_id=hire_seed["user_id"],
    )
    assert result.status == RESULT_COMMITTED
    assert _open_blocker_count(hire_seed["application_id"], BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE) == 0
    assert _open_blocker_count(hire_seed["application_id"], BLOCKER_CODE_PHOTO_CANONICALIZATION_FAILED) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_resolve_failure_then_retry_via_ledger_replay_clears_blockers(monkeypatch, hire_seed) -> None:
    from app.person_photos.application import hire_apply_hook as hook_module

    file_id = uuid4().hex
    _set_draft_photo_file_id(hire_seed["application_id"], file_id)
    _save_intake_photo(hire_seed["application_id"], file_id, make_hire_test_jpeg())

    real_resolve = hook_module._resolve_photo_blockers_durable
    resolve_calls = {"count": 0}

    def failing_resolve_once(**kwargs) -> None:
        resolve_calls["count"] += 1
        if resolve_calls["count"] == 1:
            raise RuntimeError("resolve failed")
        real_resolve(**kwargs)

    monkeypatch.setattr(hook_module, "_resolve_photo_blockers_durable", failing_resolve_once)

    with pytest.raises(RuntimeError, match="resolve failed"):
        ensure_hire_photo_ready(
            application_id=hire_seed["application_id"],
            person_id=hire_seed["person_id"],
            actor_user_id=hire_seed["user_id"],
        )

    with engine.connect() as conn:
        canonical_count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_photos WHERE person_id = :person_id"),
            {"person_id": hire_seed["person_id"]},
        ).scalar_one()
    assert int(canonical_count) == 1

    result = ensure_hire_photo_ready(
        application_id=hire_seed["application_id"],
        person_id=hire_seed["person_id"],
        actor_user_id=hire_seed["user_id"],
    )
    assert result.status == RESULT_IDEMPOTENT_OK
    assert _open_blocker_count(hire_seed["application_id"], BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE) == 0
    assert _open_blocker_count(hire_seed["application_id"], BLOCKER_CODE_PHOTO_CANONICALIZATION_FAILED) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_successful_canonicalization_uses_hire_apply_mode(hire_seed) -> None:
    file_id = uuid4().hex
    _set_draft_photo_file_id(hire_seed["application_id"], file_id)
    _save_intake_photo(hire_seed["application_id"], file_id, make_hire_test_jpeg())

    ensure_hire_photo_ready(
        application_id=hire_seed["application_id"],
        person_id=hire_seed["person_id"],
        actor_user_id=hire_seed["user_id"],
    )

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT canonicalization_mode
                FROM public.person_photo_sources
                WHERE source_application_id = :application_id
                LIMIT 1
                """
            ),
            {"application_id": hire_seed["application_id"]},
        ).scalar_one()
    assert row == CANONICALIZATION_MODE_HIRE_APPLY


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_non_hire_order_apply_skips_photo_hook(monkeypatch) -> None:
    from app.services.personnel_orders_apply_service import (
        OrderHireApplyPrecheck,
        apply_personnel_order,
    )

    called = False

    def fake_ensure_hire_photo_ready(**_kwargs) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.person_photos.application.hire_apply_hook.ensure_hire_photo_ready",
        fake_ensure_hire_photo_ready,
    )
    monkeypatch.setattr(
        "app.services.personnel_orders_apply_service.precheck_order_hire_apply",
        lambda _order_id: OrderHireApplyPrecheck(
            order_id=99,
            order_type_code="TRANSFER",
            already_applied=False,
            linked_application_id=1,
            linked_person_id=1,
        ),
    )
    monkeypatch.setattr(
        "app.services.personnel_orders_apply_service.apply_personnel_order_in_conn",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.personnel_orders_apply_service.get_personnel_order",
        lambda _order_id: {"order_id": 99},
    )
    monkeypatch.setattr(
        "app.services.personnel_orders_apply_service._require_available",
        lambda: None,
    )

    apply_personnel_order(order_id=99, created_by=1)
    assert called is False


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_already_applied_order_skips_photo_hook(monkeypatch) -> None:
    from app.services.personnel_orders_apply_service import (
        OrderHireApplyPrecheck,
        PersonnelOrderAlreadyAppliedError,
        apply_personnel_order,
    )

    called = False

    def fake_ensure_hire_photo_ready(**_kwargs) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.person_photos.application.hire_apply_hook.ensure_hire_photo_ready",
        fake_ensure_hire_photo_ready,
    )
    monkeypatch.setattr(
        "app.services.personnel_orders_apply_service.precheck_order_hire_apply",
        lambda _order_id: OrderHireApplyPrecheck(
            order_id=99,
            order_type_code="HIRE",
            already_applied=True,
            linked_application_id=1,
            linked_person_id=1,
        ),
    )

    with pytest.raises(PersonnelOrderAlreadyAppliedError):
        apply_personnel_order(order_id=99, created_by=1)
    assert called is False


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_concurrent_missing_photo_retries_leave_single_open_blocker(hire_seed) -> None:
    import threading

    barrier = threading.Barrier(2)
    results: list[Exception | None] = []

    def _attempt() -> None:
        barrier.wait()
        try:
            ensure_hire_photo_ready(
                application_id=hire_seed["application_id"],
                person_id=hire_seed["person_id"],
                actor_user_id=hire_seed["user_id"],
            )
            results.append(None)
        except Exception as exc:
            results.append(exc)

    threads = [threading.Thread(target=_attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 2
    assert all(isinstance(item, HirePhotoNotReadyError) for item in results if item is not None)
    assert results.count(None) == 0
    assert _open_blocker_count(hire_seed["application_id"], BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE) == 1
    assert _open_blocker_count(hire_seed["application_id"], BLOCKER_CODE_PHOTO_CANONICALIZATION_FAILED) == 0

    with engine.connect() as conn:
        photo_count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_photos WHERE person_id = :person_id"),
            {"person_id": hire_seed["person_id"]},
        ).scalar_one()
        source_count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_photo_sources WHERE person_id = :person_id"),
            {"person_id": hire_seed["person_id"]},
        ).scalar_one()
    assert int(photo_count) == 0
    assert int(source_count) == 0
