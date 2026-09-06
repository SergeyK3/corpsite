#!/usr/bin/env python3
"""Safely import canonical personnel JPEGs from a reviewed JSON manifest.

Dry-run is the default. The write path is deliberately delegated to
``manual_upload_service``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.engine import engine as default_engine
from app.person_photos.application.manual_upload_service import register_manual_person_photo
from app.person_photos.domain.command_ids import manual_photo_command_id
from app.person_photos.domain.models import (
    RESULT_IDEMPOTENT_OK,
    CanonicalizePersonPhotoResult,
    RegisterManualPersonPhotoRequest,
)
from app.person_photos.infrastructure.photo_storage import validate_canonical_photo_bytes
from app.person_photos.infrastructure.repository import PersonPhotoRepository
from app.personnel_intake.domain.photo_validation import INTAKE_PHOTO_MAX_BYTES

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    person_id: int
    expected_full_name: str
    jpeg_path: Path
    sha256: str
    request_id: str


@dataclass(frozen=True, slots=True)
class PersonState:
    full_name: str
    active_checksum: str | None
    request_person_id: int | None
    request_checksum: str | None


@dataclass(frozen=True, slots=True)
class CheckedEntry:
    entry: ManifestEntry
    content: bytes | None
    active_checksum: str | None
    error: str | None


def _normalized_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _required_string(item: dict, field: str, *, index: int) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"photos[{index}].{field} must be a non-empty string")
    if value != value.strip():
        raise ValueError(f"photos[{index}].{field} must not have surrounding whitespace")
    return value


def load_manifest(path: Path) -> list[ManifestEntry]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read manifest: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("manifest must be an object with version=1")
    photos = payload.get("photos")
    if not isinstance(photos, list) or not photos:
        raise ValueError("manifest photos must be a non-empty array")

    entries: list[ManifestEntry] = []
    seen_request_ids: set[str] = set()
    seen_person_ids: set[int] = set()
    manifest_dir = path.resolve().parent
    for index, item in enumerate(photos):
        if not isinstance(item, dict):
            raise ValueError(f"photos[{index}] must be an object")
        person_id = item.get("person_id")
        if isinstance(person_id, bool) or not isinstance(person_id, int) or person_id < 1:
            raise ValueError(f"photos[{index}].person_id must be a positive integer")
        full_name = _required_string(item, "expected_full_name", index=index)
        path_value = _required_string(item, "jpeg_path", index=index)
        checksum = _required_string(item, "sha256", index=index).lower()
        request_id = _required_string(item, "request_id", index=index)
        if not SHA256_RE.fullmatch(checksum):
            raise ValueError(f"photos[{index}].sha256 must contain 64 hexadecimal characters")
        if request_id in seen_request_ids:
            raise ValueError(f"duplicate request_id in manifest: {request_id}")
        if person_id in seen_person_ids:
            raise ValueError(f"duplicate person_id in manifest: {person_id}")
        seen_request_ids.add(request_id)
        seen_person_ids.add(person_id)
        jpeg_path = Path(path_value)
        if not jpeg_path.is_absolute():
            jpeg_path = manifest_dir / jpeg_path
        entries.append(
            ManifestEntry(
                person_id=person_id,
                expected_full_name=full_name,
                jpeg_path=jpeg_path.resolve(),
                sha256=checksum,
                request_id=request_id,
            )
        )
    return entries


def _inspect_person(engine: Engine, entry: ManifestEntry) -> PersonState | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT full_name FROM public.persons WHERE person_id = :person_id"),
            {"person_id": entry.person_id},
        ).mappings().first()
        if row is None:
            return None
        repo = PersonPhotoRepository(conn)
        active = repo.get_active_photo(entry.person_id)
        source = repo.find_source_by_command_id(manual_photo_command_id(entry.request_id))
        request_photo = repo.get_photo(source.person_photo_id) if source is not None else None
        return PersonState(
            full_name=str(row["full_name"]),
            active_checksum=active.checksum_sha256 if active is not None else None,
            request_person_id=source.person_id if source is not None else None,
            request_checksum=request_photo.checksum_sha256 if request_photo is not None else None,
        )


def _initiator_exists(engine: Engine, user_id: int) -> bool:
    with engine.connect() as conn:
        return (
            conn.execute(
                text("SELECT 1 FROM public.users WHERE user_id = :user_id"),
                {"user_id": user_id},
            ).first()
            is not None
        )


def _check_entry(entry: ManifestEntry, *, engine: Engine, allow_replace: bool) -> CheckedEntry:
    state: PersonState | None = None
    try:
        state = _inspect_person(engine, entry)
        if state is None:
            raise ValueError("Person does not exist")
        if _normalized_name(state.full_name) != _normalized_name(entry.expected_full_name):
            raise ValueError(f"full name mismatch (database: {state.full_name})")
        if not entry.jpeg_path.is_file():
            raise ValueError("JPEG file does not exist")
        if entry.jpeg_path.stat().st_size > INTAKE_PHOTO_MAX_BYTES:
            raise ValueError("JPEG exceeds the canonical photo size limit")
        content = entry.jpeg_path.read_bytes()
        validate_canonical_photo_bytes(content)
        actual_checksum = hashlib.sha256(content).hexdigest()
        if actual_checksum != entry.sha256:
            raise ValueError(f"checksum mismatch (actual: {actual_checksum})")
        if state.request_person_id is not None:
            if state.request_person_id != entry.person_id:
                raise ValueError("request_id was already used for another Person")
            if state.request_checksum != entry.sha256:
                raise ValueError("request_id was already used for different JPEG content")
        elif (
            state.active_checksum is not None
            and state.active_checksum != entry.sha256
            and not allow_replace
        ):
            raise ValueError("a different active photo exists; use --allow-replace")
        return CheckedEntry(entry, content, state.active_checksum, None)
    except Exception as exc:
        active_checksum = state.active_checksum if state is not None else None
        return CheckedEntry(entry, None, active_checksum, str(exc))


def _emit(check: CheckedEntry, status: str, detail: str, output: Callable[[str], None]) -> None:
    output(
        f"person_id={check.entry.person_id} | ФИО={check.entry.expected_full_name} | "
        f"checksum={check.entry.sha256} | {status} | "
        f"active={check.active_checksum or 'NONE'} | {detail}"
    )


def run_import(
    manifest_path: Path,
    *,
    apply: bool = False,
    initiator_user_id: int | None = None,
    allow_replace: bool = False,
    engine: Engine = default_engine,
    register: Callable[..., CanonicalizePersonPhotoResult] = register_manual_person_photo,
    output: Callable[[str], None] = print,
) -> int:
    if apply and (initiator_user_id is None or initiator_user_id < 1):
        raise ValueError("--apply requires a positive --initiator-user-id")
    if apply and not _initiator_exists(engine, int(initiator_user_id)):
        raise ValueError(f"initiator user_id={initiator_user_id} does not exist")

    entries = load_manifest(manifest_path)
    checked = [_check_entry(entry, engine=engine, allow_replace=allow_replace) for entry in entries]
    has_errors = any(item.error is not None for item in checked)

    if not apply:
        for item in checked:
            _emit(item, "FAILED" if item.error else "SKIPPED", item.error or "dry-run: validated", output)
        return 1 if has_errors else 0

    if has_errors:
        for item in checked:
            _emit(
                item,
                "FAILED" if item.error else "SKIPPED",
                item.error or "batch preflight failed; nothing applied",
                output,
            )
        return 1

    failed = False
    for item in checked:
        assert item.content is not None
        try:
            result = register(
                RegisterManualPersonPhotoRequest(
                    person_id=item.entry.person_id,
                    jpeg_content=item.content,
                    actor_user_id=int(initiator_user_id),
                    request_id=item.entry.request_id,
                    correlation_id=item.entry.request_id,
                    allow_replace=allow_replace,
                ),
                engine=engine,
            )
            status = "SKIPPED" if result.status == RESULT_IDEMPOTENT_OK else "CREATED"
            _emit(item, status, result.status, output)
        except Exception as exc:
            failed = True
            _emit(item, "FAILED", str(exc), output)
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="UTF-8 JSON manifest path")
    parser.add_argument("--apply", action="store_true", help="perform writes (default: dry-run)")
    parser.add_argument("--initiator-user-id", type=int, help="audited initiating user_id")
    parser.add_argument(
        "--allow-replace", action="store_true", help="allow replacing a different active photo"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_import(
            args.manifest,
            apply=args.apply,
            initiator_user_id=args.initiator_user_id,
            allow_replace=args.allow_replace,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
