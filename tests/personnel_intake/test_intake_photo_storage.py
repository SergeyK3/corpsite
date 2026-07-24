"""Unit tests for intake photo filesystem storage and archive filenames."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from app.config import PROJECT_ROOT
from app.personnel_intake.domain.photo_archive_name import (
    build_intake_photo_archive_filename,
    build_intake_photo_content_disposition,
    sanitize_intake_photo_archive_part,
)
from app.personnel_intake.infrastructure import photo_storage


def _jpeg(width: int = 600, height: int = 800) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(40, 80, 120)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_missing_storage_root_is_mandatory(monkeypatch) -> None:
    monkeypatch.delenv("PERSONNEL_PHOTO_STORAGE_ROOT", raising=False)
    with pytest.raises(RuntimeError, match="PERSONNEL_PHOTO_STORAGE_ROOT"):
        photo_storage.intake_photo_storage_root()


def test_local_relative_storage_root_resolves_under_project(monkeypatch) -> None:
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", "runtime/personnel-intake/photos")
    root = photo_storage.intake_photo_storage_root()
    assert root == PROJECT_ROOT / "runtime" / "personnel-intake" / "photos"
    assert root.as_posix().endswith("runtime/personnel-intake/photos")


def test_absolute_production_storage_root(monkeypatch, tmp_path: Path) -> None:
    prod_root = tmp_path / "var" / "lib" / "corpsite" / "personnel-photos"
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", str(prod_root))
    assert photo_storage.intake_photo_storage_root() == prod_root
    file_id = "a" * 32
    path = photo_storage.intake_photo_path(42, file_id)
    assert path == prod_root.resolve() / "42" / f"{file_id}.jpg"
    assert path.is_relative_to(prod_root.resolve())


def test_ensure_root_creates_directory_and_checks_writable(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "personnel-photos"
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", str(root))
    assert not root.exists()
    ensured = photo_storage.ensure_intake_photo_storage_root()
    assert ensured.is_dir()
    assert ensured == root.resolve()


def test_physical_path_uses_stable_file_id_not_fio(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", str(tmp_path / "photos"))
    file_id = "a" * 32
    path = photo_storage.intake_photo_path(42, file_id)
    assert path == (tmp_path / "photos").resolve() / "42" / f"{file_id}.jpg"
    assert "Иванов" not in str(path)
    assert "Ivanov" not in str(path)


def test_save_read_delete_roundtrip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", str(tmp_path / "photos"))
    file_id = "b" * 32
    content = _jpeg()
    saved = photo_storage.save_intake_photo(7, file_id, content)
    assert saved.is_file()
    assert photo_storage.read_intake_photo(7, file_id) == content
    photo_storage.delete_intake_photo(7, file_id)
    assert photo_storage.read_intake_photo(7, file_id) is None


def test_resolve_path_within_root_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path / "photos"
    root.mkdir()
    safe = photo_storage.resolve_path_within_root(root, "12", f"{'c' * 32}.jpg")
    assert safe.is_relative_to(root.resolve())
    with pytest.raises(ValueError, match="escapes storage root"):
        photo_storage.resolve_path_within_root(root, "..", "outside.jpg")
    with pytest.raises(ValueError, match="escapes storage root"):
        photo_storage.resolve_path_within_root(root, "1", "..", "..", "outside.jpg")


@pytest.mark.parametrize(
    "bad_id",
    [
        "../etc/passwd",
        "a" * 31,
        "g" * 32,
        "Иванов",
        "abc/def",
    ],
)
def test_invalid_file_id_rejected(bad_id: str) -> None:
    with pytest.raises(ValueError):
        photo_storage.normalize_intake_photo_file_id(bad_id)


def test_empty_file_id_normalizes_to_empty_and_path_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", str(tmp_path / "photos"))
    assert photo_storage.normalize_intake_photo_file_id("") == ""
    with pytest.raises(ValueError):
        photo_storage.intake_photo_path(1, "")


def test_archive_filename_keeps_cyrillic_and_uses_personnel_number() -> None:
    name = build_intake_photo_archive_filename(
        last_name="Иванов",
        first_name="Иван",
        application_id=100,
        personnel_number="ТН-0042",
    )
    assert name == "Иванов_Иван_ТН-0042.jpg"


def test_archive_filename_falls_back_to_application_id() -> None:
    name = build_intake_photo_archive_filename(
        last_name="Петров",
        first_name="Пётр",
        application_id=55,
        personnel_number="",
    )
    assert name == "Петров_Пётр_55.jpg"


def test_archive_filename_distinguishes_homonyms_by_suffix() -> None:
    first = build_intake_photo_archive_filename(
        last_name="Иванов",
        first_name="Иван",
        application_id=10,
        personnel_number="",
    )
    second = build_intake_photo_archive_filename(
        last_name="Иванов",
        first_name="Иван",
        application_id=11,
        personnel_number="",
    )
    assert first == "Иванов_Иван_10.jpg"
    assert second == "Иванов_Иван_11.jpg"
    assert first != second

    with_number = build_intake_photo_archive_filename(
        last_name="Иванов",
        first_name="Иван",
        application_id=10,
        personnel_number="1001",
    )
    assert with_number == "Иванов_Иван_1001.jpg"


def test_archive_filename_strips_forbidden_characters() -> None:
    cleaned = sanitize_intake_photo_archive_part('Ива/нов:"*?<>|')
    assert cleaned == "Иванов"
    name = build_intake_photo_archive_filename(
        last_name='Смирнов\\Тест',
        first_name="Алекс*",
        application_id=9,
        personnel_number="12:34",
    )
    assert name == "СмирновТест_Алекс_1234.jpg"
    assert "/" not in name
    assert "\\" not in name
    assert ":" not in name
    assert "*" not in name


def test_content_disposition_preserves_cyrillic_filename_star() -> None:
    header = build_intake_photo_content_disposition("Иванов_Иван_42.jpg")
    assert 'filename="photo.jpg"' in header
    assert "filename*=UTF-8''" in header
    assert "%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2" in header
