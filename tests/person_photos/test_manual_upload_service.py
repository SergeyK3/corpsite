"""Application-service contract for canonical manual Person photo registration."""
from __future__ import annotations

import io
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.person_photos import (
    CANONICALIZATION_MODE_TRANSFER,
    SOURCE_KIND_MANUAL_UPLOAD,
)
from app.person_photos.application.manual_upload_service import register_manual_person_photo
from app.person_photos.domain.errors import PhotoReplacementRequiresApprovalError
from app.person_photos.domain.models import (
    RESULT_COMMITTED,
    RegisterManualPersonPhotoRequest,
)
from app.person_photos.infrastructure.photo_storage import read_canonical_photo, sha256_hex
from app.personnel_intake.domain.errors import PersonnelIntakeValidationError
from tests.conftest import table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available


pytestmark = pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")


def _jpeg(*, color: tuple[int, int, int] = (50, 90, 130)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (600, 800), color=color).save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def photo_storage(monkeypatch, tmp_path: Path) -> Path:
    root = tmp_path / "person-photos"
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", str(root))
    return root


@pytest.fixture
def manual_seed(seed):
    with engine.begin() as conn:
        required = ("person_photos", "person_photo_sources", "personnel_record_events")
        if not all(table_exists(conn, table) for table in required):
            pytest.skip("Person photo schema missing — run: alembic upgrade head")
        person_id = insert_person(
            conn,
            full_name=f"Manual Photo {uuid4().hex[:8]}",
            prefix="manual-photo",
        )
    yield {"person_id": person_id, "user_id": seed["initiator_user_id"]}
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


def _request(manual_seed, content: bytes) -> RegisterManualPersonPhotoRequest:
    return RegisterManualPersonPhotoRequest(
        person_id=manual_seed["person_id"],
        jpeg_content=content,
        actor_user_id=manual_seed["user_id"],
        request_id=f"pytest-{uuid4().hex}",
        correlation_id=f"corr-{uuid4().hex}",
    )


def test_registers_first_manual_photo_as_active_version(manual_seed) -> None:
    result = register_manual_person_photo(_request(manual_seed, _jpeg()))

    assert result.status == RESULT_COMMITTED
    assert result.person_photo_source_id is not None
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT person_photo_id, is_active, superseded_at, uploaded_by_user_id
                FROM public.person_photos
                WHERE person_id = :person_id
                """
            ),
            {"person_id": manual_seed["person_id"]},
        ).mappings().one()
    assert int(row["person_photo_id"]) == result.person_photo_id
    assert row["is_active"] is True
    assert row["superseded_at"] is None
    assert int(row["uploaded_by_user_id"]) == manual_seed["user_id"]


def test_manual_photo_checksum_and_provenance_are_consistent(manual_seed) -> None:
    content = _jpeg(color=(10, 20, 30))
    request = _request(manual_seed, content)
    result = register_manual_person_photo(request)

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT p.storage_rel_path, p.checksum_sha256,
                       s.source_kind, s.canonicalization_mode,
                       s.source_application_id, s.source_intake_photo_file_id,
                       s.canonicalized_by_user_id, s.command_id
                FROM public.person_photos p
                JOIN public.person_photo_sources s
                  ON s.person_photo_id = p.person_photo_id
                 AND s.person_id = p.person_id
                WHERE p.person_photo_id = :person_photo_id
                """
            ),
            {"person_photo_id": result.person_photo_id},
        ).mappings().one()

    stored = read_canonical_photo(str(row["storage_rel_path"]))
    assert stored == content
    assert str(row["checksum_sha256"]).strip() == sha256_hex(content)
    assert row["source_kind"] == SOURCE_KIND_MANUAL_UPLOAD
    assert row["canonicalization_mode"] == CANONICALIZATION_MODE_TRANSFER
    assert row["source_application_id"] is None
    assert row["source_intake_photo_file_id"] is None
    assert int(row["canonicalized_by_user_id"]) == manual_seed["user_id"]
    assert row["command_id"] == result.command_id


def test_manual_photo_rejects_invalid_image_without_side_effects(
    manual_seed,
    photo_storage: Path,
) -> None:
    with pytest.raises(PersonnelIntakeValidationError):
        register_manual_person_photo(_request(manual_seed, b"not-a-jpeg"))

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_photos WHERE person_id = :person_id"),
            {"person_id": manual_seed["person_id"]},
        ).scalar_one()
    assert int(count) == 0
    assert list(photo_storage.rglob("*.jpg")) == [] if photo_storage.exists() else True


def test_manual_photo_rolls_back_db_and_file_when_provenance_insert_fails(
    monkeypatch,
    manual_seed,
    photo_storage: Path,
) -> None:
    from app.person_photos.infrastructure import repository as repository_module

    def fail_insert_source(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("forced provenance failure")

    monkeypatch.setattr(
        repository_module.PersonPhotoRepository,
        "insert_source",
        fail_insert_source,
    )

    with pytest.raises(RuntimeError, match="forced provenance failure"):
        register_manual_person_photo(_request(manual_seed, _jpeg()))

    with engine.connect() as conn:
        photo_count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_photos WHERE person_id = :person_id"),
            {"person_id": manual_seed["person_id"]},
        ).scalar_one()
        source_count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_photo_sources WHERE person_id = :person_id"),
            {"person_id": manual_seed["person_id"]},
        ).scalar_one()
    assert int(photo_count) == 0
    assert int(source_count) == 0
    assert list(photo_storage.rglob("*.jpg")) == [] if photo_storage.exists() else True


def test_manual_photo_does_not_replace_active_version_without_approval(
    manual_seed,
    photo_storage: Path,
) -> None:
    first = register_manual_person_photo(_request(manual_seed, _jpeg(color=(1, 2, 3))))

    with pytest.raises(PhotoReplacementRequiresApprovalError):
        register_manual_person_photo(_request(manual_seed, _jpeg(color=(4, 5, 6))))

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT person_photo_id, is_active
                FROM public.person_photos
                WHERE person_id = :person_id
                """
            ),
            {"person_id": manual_seed["person_id"]},
        ).mappings().all()
    assert [(int(row["person_photo_id"]), bool(row["is_active"])) for row in rows] == [
        (first.person_photo_id, True)
    ]
    assert len(list(photo_storage.rglob("*.jpg"))) == 1
