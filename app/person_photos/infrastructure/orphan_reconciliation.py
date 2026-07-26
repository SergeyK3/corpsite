"""Detect canonical photo files without DB rows."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import Connection, Engine

from app.db.engine import engine as default_engine
from app.person_photos.infrastructure.photo_storage import intake_photo_storage_root
from app.person_photos.infrastructure.repository import PersonPhotoRepository


@dataclass(frozen=True, slots=True)
class OrphanCanonicalPhotoFile:
    storage_rel_path: str
    absolute_path: Path


def find_orphan_canonical_photo_files(
    *,
    conn: Connection | None = None,
    engine: Engine = default_engine,
) -> list[OrphanCanonicalPhotoFile]:
    root = intake_photo_storage_root()
    if conn is not None:
        known_paths = PersonPhotoRepository(conn).list_storage_rel_paths()
    else:
        with engine.connect() as owned_conn:
            known_paths = PersonPhotoRepository(owned_conn).list_storage_rel_paths()

    orphans: list[OrphanCanonicalPhotoFile] = []
    person_root = root / "person"
    if not person_root.is_dir():
        return orphans

    for person_dir in person_root.iterdir():
        if not person_dir.is_dir():
            continue
        for photo_path in person_dir.glob("*.jpg"):
            rel = f"person/{person_dir.name}/{photo_path.name}"
            if rel not in known_paths:
                orphans.append(
                    OrphanCanonicalPhotoFile(storage_rel_path=rel, absolute_path=photo_path)
                )
    return orphans
