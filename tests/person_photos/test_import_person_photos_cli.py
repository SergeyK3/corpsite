"""Tests for the guarded personnel-photo manifest importer."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from app.person_photos.domain.models import RESULT_COMMITTED, RESULT_IDEMPOTENT_OK

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ops" / "import_person_photos.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("import_person_photos", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ops = _load_module()


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (600, 800), color=(20, 40, 60)).save(buffer, "JPEG", quality=85)
    return buffer.getvalue()


def _manifest(tmp_path: Path, *, full_name="Иванов Иван Иванович", checksum=None) -> Path:
    content = _jpeg()
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(content)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "photos": [
                    {
                        "person_id": 42,
                        "expected_full_name": full_name,
                        "jpeg_path": "photo.jpg",
                        "sha256": checksum or hashlib.sha256(content).hexdigest(),
                        "request_id": "photo-import-test-42",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return manifest


def _state(*, name="Иванов Иван Иванович", active=None, request_checksum=None):
    return ops.PersonState(
        full_name=name,
        active_checksum=active,
        request_person_id=42 if request_checksum else None,
        request_checksum=request_checksum,
    )


def test_dry_run_validates_without_calling_service(monkeypatch, tmp_path):
    manifest = _manifest(tmp_path)
    monkeypatch.setattr(ops, "_inspect_person", lambda engine, entry: _state())
    calls = []

    code = ops.run_import(manifest, engine=object(), register=lambda *a, **k: calls.append(a))

    assert code == 0
    assert calls == []


def test_successful_apply_calls_manual_upload_service(monkeypatch, tmp_path):
    manifest = _manifest(tmp_path)
    monkeypatch.setattr(ops, "_inspect_person", lambda engine, entry: _state())
    monkeypatch.setattr(ops, "_initiator_exists", lambda engine, user_id: True)
    requests = []

    def register(request, *, engine):
        requests.append(request)
        return SimpleNamespace(status=RESULT_COMMITTED)

    code = ops.run_import(
        manifest, apply=True, initiator_user_id=7, engine=object(), register=register
    )

    assert code == 0
    assert len(requests) == 1
    assert requests[0].person_id == 42
    assert requests[0].actor_user_id == 7
    assert requests[0].allow_replace is False


def test_wrong_full_name_fails_preflight(monkeypatch, tmp_path):
    manifest = _manifest(tmp_path, full_name="Петров Петр Петрович")
    monkeypatch.setattr(ops, "_inspect_person", lambda engine, entry: _state())

    assert ops.run_import(manifest, engine=object()) == 1


def test_wrong_checksum_fails_preflight(monkeypatch, tmp_path):
    manifest = _manifest(tmp_path, checksum="0" * 64)
    monkeypatch.setattr(ops, "_inspect_person", lambda engine, entry: _state())

    assert ops.run_import(manifest, engine=object()) == 1


def test_existing_different_photo_requires_allow_replace(monkeypatch, tmp_path):
    manifest = _manifest(tmp_path)
    monkeypatch.setattr(ops, "_inspect_person", lambda engine, entry: _state(active="1" * 64))
    monkeypatch.setattr(ops, "_initiator_exists", lambda engine, user_id: True)
    calls = []

    code = ops.run_import(
        manifest,
        apply=True,
        initiator_user_id=7,
        engine=object(),
        register=lambda *a, **k: calls.append(a),
    )

    assert code == 1
    assert calls == []


def test_repeated_request_id_is_reported_as_idempotent_skip(monkeypatch, tmp_path):
    manifest = _manifest(tmp_path)
    checksum = hashlib.sha256((tmp_path / "photo.jpg").read_bytes()).hexdigest()
    registered = False

    def inspect(engine, entry):
        if registered:
            return _state(active=checksum, request_checksum=checksum)
        return _state()

    def register(request, *, engine):
        nonlocal registered
        if registered:
            return SimpleNamespace(status=RESULT_IDEMPOTENT_OK)
        registered = True
        return SimpleNamespace(status=RESULT_COMMITTED)

    monkeypatch.setattr(ops, "_inspect_person", inspect)
    monkeypatch.setattr(ops, "_initiator_exists", lambda engine, user_id: True)
    lines = []

    first_code = ops.run_import(
        manifest,
        apply=True,
        initiator_user_id=7,
        engine=object(),
        register=register,
        output=lines.append,
    )
    second_code = ops.run_import(
        manifest,
        apply=True,
        initiator_user_id=7,
        engine=object(),
        register=register,
        output=lines.append,
    )

    assert first_code == second_code == 0
    assert any("CREATED" in line and "committed" in line for line in lines)
    assert any("SKIPPED" in line and "idempotent_ok" in line for line in lines)
