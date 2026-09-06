"""Protected read API for the active canonical Person photo."""
from __future__ import annotations

import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.db.engine import engine
from app.db.models.person_photos import MIME_TYPE_JPEG
from app.main import app
from app.person_photos.infrastructure.photo_storage import (
    canonical_photo_absolute_path,
    prepare_canonical_photo_from_bytes,
)
from app.person_photos.infrastructure.repository import PersonPhotoRepository
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import (
    cleanup_person_graph,
    insert_person,
    ppr_db_available,
    require_ppr_schema,
)


pytestmark = pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (600, 800), color=(70, 110, 150)).save(
        buffer,
        format="JPEG",
        quality=85,
    )
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _isolated_photo_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", str(tmp_path))


@pytest.fixture
def photo_schema_ready():
    with engine.connect() as conn:
        if not table_exists(conn, "person_photos"):
            pytest.skip("person_photos missing — run: alembic upgrade head")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def bare_person() -> int:
    require_ppr_schema()
    with engine.begin() as conn:
        person_id = insert_person(
            conn,
            full_name=f"Person Photo Read {uuid4().hex[:8]}",
            prefix="person-photo-read",
        )
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


def _add_active_photo(person_id: int, content: bytes) -> str:
    prepared = prepare_canonical_photo_from_bytes(person_id=person_id, content=content)
    with engine.begin() as conn:
        PersonPhotoRepository(conn).insert_photo(
            person_id=person_id,
            file_id=prepared.file_id,
            storage_rel_path=prepared.storage_rel_path,
            mime_type=MIME_TYPE_JPEG,
            byte_size=prepared.byte_size,
            checksum_sha256=prepared.checksum_sha256,
            is_active=True,
            superseded_at=None,
            uploaded_by_user_id=None,
        )
    return prepared.storage_rel_path


def test_person_photo_allowed_for_same_privileged_reader(
    client: TestClient,
    bare_person: int,
    photo_schema_ready,
    privileged_headers,
) -> None:
    content = _jpeg_bytes()
    _add_active_photo(bare_person, content)

    response = client.get(
        f"/api/ppr/persons/{bare_person}/photo",
        headers=privileged_headers,
    )

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"].startswith(MIME_TYPE_JPEG)
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "storage_rel_path" not in response.headers


def test_person_photo_denied_without_card_access(
    client: TestClient,
    bare_person: int,
    photo_schema_ready,
    seed,
) -> None:
    _add_active_photo(bare_person, _jpeg_bytes())

    response = client.get(
        f"/api/ppr/persons/{bare_person}/photo",
        headers=auth_headers(seed["executor_user_id"]),
    )

    assert response.status_code == 403


def test_person_photo_requires_authentication(
    client: TestClient,
    bare_person: int,
    photo_schema_ready,
) -> None:
    response = client.get(f"/api/ppr/persons/{bare_person}/photo")

    assert response.status_code == 401


def test_person_photo_absent_returns_404(
    client: TestClient,
    bare_person: int,
    photo_schema_ready,
    privileged_headers,
) -> None:
    response = client.get(
        f"/api/ppr/persons/{bare_person}/photo",
        headers=privileged_headers,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Person photo not found."}


def test_person_photo_unavailable_file_returns_same_404(
    client: TestClient,
    bare_person: int,
    photo_schema_ready,
    privileged_headers,
) -> None:
    storage_path = _add_active_photo(bare_person, _jpeg_bytes())
    canonical_photo_absolute_path(storage_path).unlink()

    response = client.get(
        f"/api/ppr/persons/{bare_person}/photo",
        headers=privileged_headers,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Person photo not found."}
