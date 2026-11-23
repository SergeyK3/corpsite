"""Protected manual upload API for canonical Person-card photos."""
from __future__ import annotations

import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available, require_ppr_schema


pytestmark = pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")


def _jpeg(*, color: tuple[int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (600, 800), color=color).save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _isolated_photo_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", str(tmp_path))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def photo_people(seed):
    require_ppr_schema()
    with engine.begin() as conn:
        required = ("person_photos", "person_photo_sources", "personnel_record_events")
        if not all(table_exists(conn, table) for table in required):
            pytest.skip("Person photo schema missing — run: alembic upgrade head")
        first = insert_person(conn, full_name=f"Photo API A {uuid4().hex[:8]}", prefix="photo-api-a")
        second = insert_person(conn, full_name=f"Photo API B {uuid4().hex[:8]}", prefix="photo-api-b")
    yield first, second
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[first, second], employee_ids=[])


def _post_photo(client: TestClient, *, person_id: int, content: bytes, headers, filename: str = "photo.jpg"):
    return client.post(
        f"/api/ppr/persons/{person_id}/photo",
        headers=headers,
        files={"file": (filename, content, "image/jpeg")},
    )


def test_uploads_first_photo_to_exact_card_person_id(
    client: TestClient,
    photo_people: tuple[int, int],
    privileged_headers,
) -> None:
    first, second = photo_people

    response = _post_photo(
        client,
        person_id=second,
        content=_jpeg(color=(10, 20, 30)),
        headers=privileged_headers,
        # The filename deliberately looks like another Person; it is ignored.
        filename=f"person-{first}.jpg",
    )

    assert response.status_code == 200
    assert response.json()["person_id"] == second
    with engine.connect() as conn:
        first_count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_photos WHERE person_id = :person_id"),
            {"person_id": first},
        ).scalar_one()
        target = conn.execute(
            text(
                "SELECT person_id, is_active FROM public.person_photos "
                "WHERE person_photo_id = :person_photo_id"
            ),
            {"person_photo_id": response.json()["person_photo_id"]},
        ).mappings().one()
    assert int(first_count) == 0
    assert int(target["person_id"]) == second
    assert target["is_active"] is True


def test_replaces_photo_by_superseding_old_version(
    client: TestClient,
    photo_people: tuple[int, int],
    privileged_headers,
) -> None:
    person_id, _ = photo_people
    first = _post_photo(
        client,
        person_id=person_id,
        content=_jpeg(color=(1, 2, 3)),
        headers=privileged_headers,
    )
    second = _post_photo(
        client,
        person_id=person_id,
        content=_jpeg(color=(4, 5, 6)),
        headers=privileged_headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT person_photo_id, is_active, superseded_at FROM public.person_photos "
                "WHERE person_id = :person_id ORDER BY person_photo_id"
            ),
            {"person_id": person_id},
        ).mappings().all()
    assert len(rows) == 2
    assert int(rows[0]["person_photo_id"]) == first.json()["person_photo_id"]
    assert rows[0]["is_active"] is False
    assert rows[0]["superseded_at"] is not None
    assert int(rows[1]["person_photo_id"]) == second.json()["person_photo_id"]
    assert rows[1]["is_active"] is True


def test_upload_is_forbidden_without_permission(client: TestClient, photo_people, seed) -> None:
    response = _post_photo(
        client,
        person_id=photo_people[0],
        content=_jpeg(color=(10, 20, 30)),
        headers=auth_headers(seed["executor_user_id"]),
    )

    assert response.status_code == 403


def test_upload_rejects_non_jpeg_before_creating_photo(
    client: TestClient,
    photo_people,
    privileged_headers,
) -> None:
    person_id = photo_people[0]
    response = client.post(
        f"/api/ppr/persons/{person_id}/photo",
        headers=privileged_headers,
        files={"file": ("invalid.png", b"not a jpeg", "image/png")},
    )

    assert response.status_code == 422
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_photos WHERE person_id = :person_id"),
            {"person_id": person_id},
        ).scalar_one()
    assert int(count) == 0
