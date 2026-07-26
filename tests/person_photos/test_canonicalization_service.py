"""Integration tests for WP-ADR061-001C person photo canonicalization."""
from __future__ import annotations

import io
import threading
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.person_photos import (
    CANONICALIZATION_MODE_HIRE_APPLY,
    CANONICALIZATION_MODE_TRANSFER,
    SOURCE_KIND_INTAKE,
)
from app.person_photos.application.canonicalization_service import canonicalize_person_photo
from app.person_photos.domain.command_ids import intake_photo_command_id
from app.person_photos.domain.errors import (
    ApplicationPersonMismatchError,
    CanonicalFileCollisionError,
    CanonicalFileMissingError,
    LedgerPersonMismatchError,
)
from app.person_photos.domain.models import (
    CanonicalizeIntakePhotoRequest,
    MUTATION_KIND_INSERT,
    MUTATION_KIND_LINK,
    MUTATION_KIND_SUPERSEDE,
    RESULT_COMMITTED,
    RESULT_IDEMPOTENT_OK,
    RESULT_PROVENANCE_LINKED,
    SECTION_CODE_PPR_PHOTO,
)
from app.person_photos.infrastructure.photo_storage import (
    canonical_photo_absolute_path,
    prepare_canonical_photo_from_bytes,
    read_canonical_photo,
    sha256_hex,
)
from app.personnel_intake.infrastructure import photo_storage as intake_photo_storage
from tests.conftest import table_exists
from tests.ppr.conftest import insert_person, ppr_db_available


def _require_schema() -> None:
    with engine.begin() as conn:
        required = (
            "person_photos",
            "person_photo_sources",
            "personnel_applications",
            "personnel_record_events",
        )
        if not all(table_exists(conn, name) for name in required):
            pytest.skip("WP-ADR061 schema missing — run: alembic upgrade head")


def _jpeg(*, color: tuple[int, int, int] = (40, 80, 120)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (600, 800), color=color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _file_id() -> str:
    return uuid4().hex


@pytest.fixture
def photo_env(monkeypatch, tmp_path: Path):
    root = tmp_path / "photos"
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", str(root))
    intake_photo_storage.ensure_intake_photo_storage_root()
    return root


@pytest.fixture
def seed(photo_env):
    _require_schema()
    with engine.begin() as conn:
        user_row = conn.execute(text("SELECT user_id FROM public.users LIMIT 1")).mappings().first()
        if user_row is None:
            pytest.skip("users table empty")
        user_id = int(user_row["user_id"])
        person_id = insert_person(conn, full_name=f"ADR061C {uuid4().hex[:8]}")
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
    return {
        "person_id": person_id,
        "application_id": int(app_row["application_id"]),
        "user_id": user_id,
        "storage_root": photo_env,
    }


def _save_intake(application_id: int, file_id: str, content: bytes) -> None:
    intake_photo_storage.save_intake_photo(application_id, file_id, content)


def _request(seed, *, file_id: str, mode: str = CANONICALIZATION_MODE_TRANSFER):
    return CanonicalizeIntakePhotoRequest(
        person_id=seed["person_id"],
        application_id=seed["application_id"],
        intake_photo_file_id=file_id,
        canonicalization_mode=mode,
        actor_user_id=seed["user_id"],
        correlation_id=f"corr-{uuid4().hex[:8]}",
    )


def _count_sources(application_id: int, file_id: str) -> int:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM public.person_photo_sources
                WHERE source_application_id = :application_id
                  AND source_intake_photo_file_id = :file_id
                """
            ),
            {"application_id": application_id, "file_id": file_id},
        ).mappings().one()
        return int(row["cnt"])


def _active_photo(person_id: int):
    with engine.connect() as conn:
        return conn.execute(
            text(
                """
                SELECT person_photo_id, storage_rel_path, checksum_sha256, is_active
                FROM public.person_photos
                WHERE person_id = :person_id AND is_active = TRUE
                """
            ),
            {"person_id": person_id},
        ).mappings().first()


def _ppr_events(person_id: int, command_id: str) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT event_id, event_type, record_table_name, event_payload
                FROM public.personnel_record_events
                WHERE person_id = :person_id
                  AND event_payload ->> 'command_id' = :command_id
                ORDER BY event_id
                """
            ),
            {"person_id": person_id, "command_id": command_id},
        ).mappings().all()
        return [dict(row) for row in rows]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_first_photo_creates_active_row_file_and_ppr_event(seed) -> None:
    file_id = _file_id()
    content = _jpeg()
    _save_intake(seed["application_id"], file_id, content)
    command_id = intake_photo_command_id(seed["application_id"], file_id)

    result = canonicalize_person_photo(_request(seed, file_id=file_id))

    assert result.status == RESULT_COMMITTED
    assert result.person_photo_source_id is not None
    active = _active_photo(seed["person_id"])
    assert active is not None
    assert active["is_active"] is True
    assert read_canonical_photo(str(active["storage_rel_path"])) is not None
    assert sha256_hex(content) == str(active["checksum_sha256"])
    events = _ppr_events(seed["person_id"], command_id)
    assert len(events) == 1
    assert events[0]["event_type"] == "PPR_SECTION_ADDED"
    assert events[0]["record_table_name"] == "person_photos"
    assert events[0]["event_payload"]["section_code"] == SECTION_CODE_PPR_PHOTO
    assert events[0]["event_payload"]["mutation_kind"] == MUTATION_KIND_INSERT


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_replacement_supersedes_prior_and_adds_new_version(seed) -> None:
    first_id = _file_id()
    second_id = _file_id()
    _save_intake(seed["application_id"], first_id, _jpeg(color=(10, 20, 30)))
    _save_intake(seed["application_id"], second_id, _jpeg(color=(200, 100, 50)))

    first = canonicalize_person_photo(_request(seed, file_id=first_id))
    second = canonicalize_person_photo(_request(seed, file_id=second_id))

    assert first.status == RESULT_COMMITTED
    assert second.status == RESULT_COMMITTED
    assert first.person_photo_id != second.person_photo_id

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT person_photo_id, is_active, superseded_at IS NOT NULL AS terminal
                FROM public.person_photos
                WHERE person_id = :person_id
                ORDER BY person_photo_id
                """
            ),
            {"person_id": seed["person_id"]},
        ).mappings().all()
    assert len(rows) == 2
    assert rows[0]["is_active"] is False and rows[0]["terminal"] is True
    assert rows[1]["is_active"] is True and rows[1]["terminal"] is False

    cmd2 = intake_photo_command_id(seed["application_id"], second_id)
    events = _ppr_events(seed["person_id"], cmd2)
    kinds = {row["event_payload"]["mutation_kind"] for row in events}
    assert MUTATION_KIND_SUPERSEDE in kinds
    assert MUTATION_KIND_INSERT in kinds


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_same_sha_adds_provenance_only(seed) -> None:
    file_a = _file_id()
    file_b = _file_id()
    content = _jpeg(color=(55, 66, 77))
    _save_intake(seed["application_id"], file_a, content)
    _save_intake(seed["application_id"], file_b, content)

    first = canonicalize_person_photo(_request(seed, file_id=file_a))
    second = canonicalize_person_photo(_request(seed, file_id=file_b))

    assert first.status == RESULT_COMMITTED
    assert second.status == RESULT_PROVENANCE_LINKED
    assert second.person_photo_id == first.person_photo_id
    assert _count_sources(seed["application_id"], file_a) == 1
    assert _count_sources(seed["application_id"], file_b) == 1

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_photos WHERE person_id = :person_id"),
            {"person_id": seed["person_id"]},
        ).scalar()
    assert int(count) == 1

    cmd_b = intake_photo_command_id(seed["application_id"], file_b)
    events = _ppr_events(seed["person_id"], cmd_b)
    assert len(events) == 1
    assert events[0]["event_payload"]["mutation_kind"] == MUTATION_KIND_LINK


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_replay_is_idempotent_when_file_intact(seed) -> None:
    file_id = _file_id()
    _save_intake(seed["application_id"], file_id, _jpeg())
    req = _request(seed, file_id=file_id)

    first = canonicalize_person_photo(req)
    second = canonicalize_person_photo(req)

    assert first.status == RESULT_COMMITTED
    assert second.status == RESULT_IDEMPOTENT_OK
    assert second.person_photo_id == first.person_photo_id
    assert _count_sources(seed["application_id"], file_id) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_replay_rejects_person_mismatch(seed) -> None:
    file_id = _file_id()
    _save_intake(seed["application_id"], file_id, _jpeg())
    canonicalize_person_photo(_request(seed, file_id=file_id))

    with engine.begin() as conn:
        other_person = insert_person(conn, full_name=f"ADR061C other {uuid4().hex[:6]}")

    with pytest.raises(LedgerPersonMismatchError):
        canonicalize_person_photo(
            CanonicalizeIntakePhotoRequest(
                person_id=other_person,
                application_id=seed["application_id"],
                intake_photo_file_id=file_id,
                canonicalization_mode=CANONICALIZATION_MODE_TRANSFER,
                actor_user_id=seed["user_id"],
            )
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_replay_rejects_missing_canonical_file(seed) -> None:
    file_id = _file_id()
    _save_intake(seed["application_id"], file_id, _jpeg())
    result = canonicalize_person_photo(_request(seed, file_id=file_id))
    active = _active_photo(seed["person_id"])
    assert active is not None
    canonical_photo_absolute_path(str(active["storage_rel_path"])).unlink()

    with pytest.raises(CanonicalFileMissingError):
        canonicalize_person_photo(_request(seed, file_id=file_id))

    assert result.person_photo_id == int(active["person_photo_id"])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_concurrent_canonicalize_same_intake_material(seed) -> None:
    file_id = _file_id()
    _save_intake(seed["application_id"], file_id, _jpeg())
    req = _request(seed, file_id=file_id)
    barrier = threading.Barrier(2)
    results: list = []
    errors: list[BaseException] = []
    intake_photo_storage.ensure_intake_photo_storage_root()

    def worker() -> None:
        try:
            barrier.wait(timeout=5)
            results.append(canonicalize_person_photo(req))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(results) == 2
    statuses = {item.status for item in results}
    assert statuses <= {RESULT_COMMITTED, RESULT_IDEMPOTENT_OK}
    assert _count_sources(seed["application_id"], file_id) == 1
    assert _active_photo(seed["person_id"]) is not None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_db_failure_deletes_prepared_file(monkeypatch, seed) -> None:
    from app.person_photos.infrastructure import repository as repo_module

    file_id = _file_id()
    _save_intake(seed["application_id"], file_id, _jpeg())

    def failing_insert_source(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("forced db failure")

    monkeypatch.setattr(repo_module.PersonPhotoRepository, "insert_source", failing_insert_source)

    with pytest.raises(RuntimeError, match="forced db failure"):
        canonicalize_person_photo(_request(seed, file_id=file_id))

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_photos WHERE person_id = :person_id"),
            {"person_id": seed["person_id"]},
        ).scalar()
    assert int(count) == 0

    person_dir = seed["storage_root"] / "person" / str(seed["person_id"])
    if person_dir.exists():
        assert list(person_dir.glob("*.jpg")) == []


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_atomic_storage_uses_person_scoped_path(seed) -> None:
    file_id = _file_id()
    _save_intake(seed["application_id"], file_id, _jpeg())
    result = canonicalize_person_photo(_request(seed, file_id=file_id))
    assert result.storage_rel_path is not None
    assert result.storage_rel_path.startswith(f"person/{seed['person_id']}/")
    assert str(seed["application_id"]) not in result.storage_rel_path


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_ppr_event_payload_matches_rev3_contract(seed) -> None:
    file_id = _file_id()
    _save_intake(seed["application_id"], file_id, _jpeg(color=(1, 2, 3)))
    command_id = intake_photo_command_id(seed["application_id"], file_id)
    result = canonicalize_person_photo(
        _request(seed, file_id=file_id, mode=CANONICALIZATION_MODE_HIRE_APPLY)
    )
    events = _ppr_events(seed["person_id"], command_id)
    payload = events[0]["event_payload"]
    assert payload["person_photo_id"] == result.person_photo_id
    assert payload["source_kind"] == SOURCE_KIND_INTAKE
    assert payload["canonicalization_mode"] == CANONICALIZATION_MODE_HIRE_APPLY
    assert payload["source_application_id"] == seed["application_id"]
    assert payload["source_intake_photo_file_id"] == file_id
    assert payload["section_code"] == SECTION_CODE_PPR_PHOTO


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_orphan_reconciliation_detects_file_without_db_row(seed) -> None:
    from app.person_photos.infrastructure.orphan_reconciliation import find_orphan_canonical_photo_files

    rel = f"person/{seed['person_id']}/{_file_id()}.jpg"
    path = canonical_photo_absolute_path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_jpeg())

    with engine.connect() as conn:
        orphans = find_orphan_canonical_photo_files(conn=conn)

    assert any(item.storage_rel_path == rel for item in orphans)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_replay_succeeds_after_intake_file_deleted(seed) -> None:
    file_id = _file_id()
    _save_intake(seed["application_id"], file_id, _jpeg())
    req = _request(seed, file_id=file_id)

    first = canonicalize_person_photo(req)
    intake_photo_storage.delete_intake_photo(seed["application_id"], file_id)

    second = canonicalize_person_photo(req)

    assert first.status == RESULT_COMMITTED
    assert second.status == RESULT_IDEMPOTENT_OK
    assert second.person_photo_id == first.person_photo_id
    assert _count_sources(seed["application_id"], file_id) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_first_canonicalization_rejects_application_person_mismatch(seed) -> None:
    file_id = _file_id()
    _save_intake(seed["application_id"], file_id, _jpeg())
    command_id = intake_photo_command_id(seed["application_id"], file_id)

    with engine.begin() as conn:
        other_person = insert_person(conn, full_name=f"ADR061C mismatch {uuid4().hex[:6]}")

    with pytest.raises(ApplicationPersonMismatchError, match="does not belong"):
        canonicalize_person_photo(
            CanonicalizeIntakePhotoRequest(
                person_id=other_person,
                application_id=seed["application_id"],
                intake_photo_file_id=file_id,
                canonicalization_mode=CANONICALIZATION_MODE_TRANSFER,
                actor_user_id=seed["user_id"],
            )
        )

    assert _active_photo(other_person) is None
    assert _active_photo(seed["person_id"]) is None
    assert _count_sources(seed["application_id"], file_id) == 0
    assert _ppr_events(other_person, command_id) == []
    assert _ppr_events(seed["person_id"], command_id) == []

    person_dir = seed["storage_root"] / "person" / str(other_person)
    if person_dir.exists():
        assert list(person_dir.glob("*.jpg")) == []


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_commit_failure_deletes_prepared_file(monkeypatch, seed) -> None:
    from sqlalchemy.engine.base import RootTransaction

    file_id = _file_id()
    _save_intake(seed["application_id"], file_id, _jpeg())
    commit_failures = {"count": 0}
    original_commit = RootTransaction.commit

    def patched_commit(self) -> None:  # type: ignore[no-untyped-def]
        commit_failures["count"] += 1
        if commit_failures["count"] >= 2:
            raise RuntimeError("commit failed")
        return original_commit(self)

    monkeypatch.setattr(RootTransaction, "commit", patched_commit)

    with pytest.raises(RuntimeError, match="commit failed"):
        canonicalize_person_photo(_request(seed, file_id=file_id))

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_photos WHERE person_id = :person_id"),
            {"person_id": seed["person_id"]},
        ).scalar()
    assert int(count) == 0

    person_dir = seed["storage_root"] / "person" / str(seed["person_id"])
    if person_dir.exists():
        assert list(person_dir.glob("*.jpg")) == []


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_db_error_not_masked_by_delete_failure(monkeypatch, seed) -> None:
    from sqlalchemy.engine.base import RootTransaction

    file_id = _file_id()
    _save_intake(seed["application_id"], file_id, _jpeg())
    commit_failures = {"count": 0}
    original_commit = RootTransaction.commit

    def patched_commit(self) -> None:  # type: ignore[no-untyped-def]
        commit_failures["count"] += 1
        if commit_failures["count"] >= 2:
            raise RuntimeError("commit failed")
        return original_commit(self)

    def failing_delete(_storage_rel_path: str) -> None:
        raise OSError("delete failed")

    monkeypatch.setattr(RootTransaction, "commit", patched_commit)
    monkeypatch.setattr(
        "app.person_photos.application.canonicalization_service.delete_canonical_photo_file",
        failing_delete,
    )

    with pytest.raises(RuntimeError, match="commit failed"):
        canonicalize_person_photo(_request(seed, file_id=file_id))


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_provenance_commit_succeeds_when_orphan_delete_fails(monkeypatch, seed) -> None:
    file_a = _file_id()
    file_b = _file_id()
    content = _jpeg(color=(55, 66, 77))
    _save_intake(seed["application_id"], file_a, content)
    _save_intake(seed["application_id"], file_b, content)

    first = canonicalize_person_photo(_request(seed, file_id=file_a))
    assert first.status == RESULT_COMMITTED

    def failing_delete(_storage_rel_path: str) -> None:
        raise OSError("delete failed")

    monkeypatch.setattr(
        "app.person_photos.application.canonicalization_service.delete_canonical_photo_file",
        failing_delete,
    )

    second = canonicalize_person_photo(_request(seed, file_id=file_b))

    assert second.status == RESULT_PROVENANCE_LINKED
    assert second.person_photo_id == first.person_photo_id
    assert _count_sources(seed["application_id"], file_a) == 1
    assert _count_sources(seed["application_id"], file_b) == 1

    cmd_b = intake_photo_command_id(seed["application_id"], file_b)
    events = _ppr_events(seed["person_id"], cmd_b)
    assert len(events) == 1
    assert events[0]["event_payload"]["mutation_kind"] == MUTATION_KIND_LINK


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_file_id_collision_does_not_overwrite_existing_file(seed) -> None:
    file_id = _file_id()
    first_content = _jpeg(color=(10, 20, 30))
    second_content = _jpeg(color=(200, 100, 50))

    first = prepare_canonical_photo_from_bytes(
        person_id=seed["person_id"],
        content=first_content,
        file_id=file_id,
    )
    assert read_canonical_photo(first.storage_rel_path) == first_content

    with pytest.raises(CanonicalFileCollisionError, match="already exists"):
        prepare_canonical_photo_from_bytes(
            person_id=seed["person_id"],
            content=second_content,
            file_id=file_id,
        )

    assert read_canonical_photo(first.storage_rel_path) == first_content
    assert sha256_hex(first_content) == sha256_hex(read_canonical_photo(first.storage_rel_path))
