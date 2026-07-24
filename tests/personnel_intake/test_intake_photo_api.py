# tests/personnel_intake/test_intake_photo_api.py
"""API tests for intake applicant photo upload (public + HR on-behalf)."""
from __future__ import annotations

import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.db.engine import engine
from app.main import app
from app.personnel_applications.domain.status import VACANCY_CHECK_CONFIRMED_VISUALLY
from app.personnel_intake.domain.models import empty_intake_draft_payload
from app.personnel_intake.infrastructure.photo_storage import intake_photo_path, read_intake_photo
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import cleanup_person_graph, ppr_db_available


def _unique_iin() -> str:
    return f"8{uuid4().int % 10_000_000_000_000:011d}"[:12]


def _make_jpeg_bytes(*, width: int = 600, height: int = 800, quality: int = 85) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(90, 120, 160)).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _make_large_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    image = Image.new("RGB", (600, 800), color=(200, 50, 50))
    image.save(buf, format="JPEG", quality=100)
    content = buf.getvalue()
    if len(content) <= 500 * 1024:
        buf = io.BytesIO()
        noisy = Image.effect_noise((600, 800), 64).convert("RGB")
        noisy.save(buf, format="JPEG", quality=100)
        content = buf.getvalue()
    assert len(content) > 500 * 1024
    return content


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def intake_schema_ready():
    if not ppr_db_available():
        pytest.skip("PostgreSQL not available")
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_intake_links"):
            pytest.skip("personnel_intake_links missing — run: alembic upgrade head")


@pytest.fixture(autouse=True)
def _photo_storage_root(monkeypatch, tmp_path_factory):
    """All photo API tests use an isolated PERSONNEL_PHOTO_STORAGE_ROOT."""
    root = tmp_path_factory.mktemp("personnel-photos")
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", str(root))
    return root


def _register_application(client, headers, *, iin: str | None = None) -> dict:
    iin = iin or _unique_iin()
    payload = {
        "iin": iin,
        "full_name": "Photo Test Applicant",
        "application_received_at": "2026-07-17",
        "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
        "idempotency_key": f"intake-photo-{uuid4().hex}",
    }
    reg = client.post("/directory/personnel-applications", json=payload, headers=headers)
    assert reg.status_code == 200, reg.text
    return reg.json()


def _issue_intake_token(client, headers, app_id: int) -> str:
    issue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=headers,
    )
    assert issue.status_code == 200, issue.text
    return issue.json()["intake_url_path"].split("/intake/")[-1]


def _upload_public_photo(client, token: str, content: bytes, *, content_type: str = "image/jpeg"):
    return client.put(
        f"/intake/{token}/photo",
        files={"file": ("photo.jpg", content, content_type)},
    )


def test_intake_photo_routes_registered(client) -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/intake/{token}/photo" in paths
    assert "/directory/personnel-applications/{application_id}/intake/photo" in paths


def test_public_photo_upload_get_replace_delete(
    client,
    intake_schema_ready,
    privileged_headers,
) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]
    token = _issue_intake_token(client, privileged_headers, app_id)
    client.get(f"/intake/{token}")

    content = _make_jpeg_bytes()
    first = _upload_public_photo(client, token, content)
    assert first.status_code == 200, first.text
    first_body = first.json()
    first_id = first_body["photo_file_id"]
    assert first_id
    assert len(first_id) == 32
    assert first_body["payload"]["personal"]["photo_file_id"] == first_id
    first_path = intake_photo_path(app_id, first_id)
    assert first_path.is_file()
    assert first_path.parent.name == str(app_id)
    assert first_path.name == f"{first_id}.jpg"

    get_res = client.get(f"/intake/{token}/photo")
    assert get_res.status_code == 200
    assert get_res.headers["content-type"].startswith("image/jpeg")
    assert get_res.content == content

    second_content = _make_jpeg_bytes(quality=70)
    second = _upload_public_photo(client, token, second_content)
    assert second.status_code == 200, second.text
    second_id = second.json()["photo_file_id"]
    assert second_id != first_id
    assert read_intake_photo(app_id, second_id) == second_content
    assert read_intake_photo(app_id, first_id) is None
    assert not first_path.is_file()

    delete_res = client.delete(f"/intake/{token}/photo")
    assert delete_res.status_code == 200, delete_res.text
    assert delete_res.json()["photo_file_id"] == ""
    assert delete_res.json()["payload"]["personal"]["photo_file_id"] == ""
    assert read_intake_photo(app_id, second_id) is None

    missing = client.get(f"/intake/{token}/photo")
    assert missing.status_code == 404

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_public_photo_archive_filename_cyrillic_and_homonyms(
    client,
    intake_schema_ready,
    privileged_headers,
) -> None:
    person_ids: list[int] = []

    first_reg = _register_application(client, privileged_headers)
    second_reg = _register_application(client, privileged_headers)
    person_ids.extend([first_reg["person_id"], second_reg["person_id"]])

    first_token = _issue_intake_token(client, privileged_headers, first_reg["application_id"])
    second_token = _issue_intake_token(client, privileged_headers, second_reg["application_id"])
    client.get(f"/intake/{first_token}")
    client.get(f"/intake/{second_token}")

    for token, app_id, personnel_number in (
        (first_token, first_reg["application_id"], ""),
        (second_token, second_reg["application_id"], "ТН-77"),
    ):
        payload = empty_intake_draft_payload()
        payload["personal"]["last_name"] = "Иванов"
        payload["personal"]["first_name"] = "Иван"
        payload["personal"]["personnel_number"] = personnel_number
        client.patch(f"/intake/{token}", json={"payload": payload})
        upload = _upload_public_photo(client, token, _make_jpeg_bytes())
        assert upload.status_code == 200, upload.text
        photo_id = upload.json()["photo_file_id"]
        stored = intake_photo_path(app_id, photo_id)
        assert stored.name == f"{photo_id}.jpg"
        assert "Иванов" not in stored.name

    from urllib.parse import unquote

    from app.personnel_intake.domain.photo_archive_name import build_intake_photo_archive_filename

    first_get = client.get(f"/intake/{first_token}/photo")
    second_get = client.get(f"/intake/{second_token}/photo")
    assert first_get.status_code == 200
    assert second_get.status_code == 200

    first_disp = unquote(first_get.headers["content-disposition"])
    second_disp = unquote(second_get.headers["content-disposition"])
    assert (
        build_intake_photo_archive_filename(
            last_name="Иванов",
            first_name="Иван",
            application_id=first_reg["application_id"],
            personnel_number="",
        )
        in first_disp
    )
    assert (
        build_intake_photo_archive_filename(
            last_name="Иванов",
            first_name="Иван",
            application_id=second_reg["application_id"],
            personnel_number="ТН-77",
        )
        in second_disp
    )
    assert first_disp != second_disp

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_public_photo_missing_or_corrupt_file_returns_404(
    client,
    intake_schema_ready,
    privileged_headers,
) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]
    token = _issue_intake_token(client, privileged_headers, app_id)
    client.get(f"/intake/{token}")

    upload = _upload_public_photo(client, token, _make_jpeg_bytes())
    assert upload.status_code == 200, upload.text
    photo_id = upload.json()["photo_file_id"]
    path = intake_photo_path(app_id, photo_id)
    path.write_bytes(b"not-a-jpeg-payload")

    corrupt = client.get(f"/intake/{token}/photo")
    assert corrupt.status_code == 404

    path.unlink(missing_ok=True)
    missing = client.get(f"/intake/{token}/photo")
    assert missing.status_code == 404

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_public_photo_rejects_invalid_files(client, intake_schema_ready, privileged_headers) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    token = _issue_intake_token(client, privileged_headers, reg["application_id"])
    client.get(f"/intake/{token}")

    svg = _upload_public_photo(
        client,
        token,
        b"<svg xmlns='http://www.w3.org/2000/svg'><rect width='10' height='10'/></svg>",
        content_type="image/svg+xml",
    )
    assert svg.status_code == 422

    wrong_size = _upload_public_photo(client, token, _make_jpeg_bytes(width=640, height=800))
    assert wrong_size.status_code == 422

    too_large = _upload_public_photo(client, token, _make_large_jpeg_bytes())
    assert too_large.status_code == 422

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_public_photo_denied_for_invalid_token(client, intake_schema_ready) -> None:
    denied = _upload_public_photo(client, "not-a-valid-token-value", _make_jpeg_bytes())
    assert denied.status_code == 403


def test_on_behalf_photo_upload_requires_personnel_admin(
    client,
    intake_schema_ready,
    privileged_headers,
    seed,
) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]
    token = _issue_intake_token(client, privileged_headers, app_id)
    client.get(f"/intake/{token}")

    denied = client.put(
        f"/directory/personnel-applications/{app_id}/intake/photo",
        headers=auth_headers(seed["executor_user_id"]),
        files={"file": ("photo.jpg", _make_jpeg_bytes(), "image/jpeg")},
    )
    assert denied.status_code == 403

    allowed = client.put(
        f"/directory/personnel-applications/{app_id}/intake/photo",
        headers=privileged_headers,
        files={"file": ("photo.jpg", _make_jpeg_bytes(), "image/jpeg")},
    )
    assert allowed.status_code == 200, allowed.text
    photo_id = allowed.json()["photo_file_id"]
    assert photo_id

    get_res = client.get(
        f"/directory/personnel-applications/{app_id}/intake/photo",
        headers=privileged_headers,
    )
    assert get_res.status_code == 200
    assert get_res.headers["content-type"].startswith("image/jpeg")

    delete_res = client.delete(
        f"/directory/personnel-applications/{app_id}/intake/photo",
        headers=privileged_headers,
    )
    assert delete_res.status_code == 200, delete_res.text
    assert delete_res.json()["payload"]["personal"]["photo_file_id"] == ""

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_on_behalf_photo_not_found_for_foreign_application(
    client,
    intake_schema_ready,
    privileged_headers,
) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])

    missing = client.put(
        f"/directory/personnel-applications/{reg['application_id'] + 999_999}/intake/photo",
        headers=privileged_headers,
        files={"file": ("photo.jpg", _make_jpeg_bytes(), "image/jpeg")},
    )
    assert missing.status_code == 404

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_photo_file_id_persisted_in_draft_payload(client, intake_schema_ready, privileged_headers) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]
    token = _issue_intake_token(client, privileged_headers, app_id)
    client.get(f"/intake/{token}")

    payload = empty_intake_draft_payload()
    payload["personal"]["last_name"] = "Фото"
    payload["personal"]["first_name"] = "Тест"
    client.patch(f"/intake/{token}", json={"payload": payload})

    upload = _upload_public_photo(client, token, _make_jpeg_bytes())
    assert upload.status_code == 200, upload.text
    photo_id = upload.json()["photo_file_id"]

    reopen = client.get(f"/intake/{token}")
    assert reopen.status_code == 200, reopen.text
    assert reopen.json()["payload"]["personal"]["photo_file_id"] == photo_id

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])
