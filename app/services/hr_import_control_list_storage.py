"""Persistent storage for HR control list upload files."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.config import PROJECT_ROOT, env
from app.db.models.hr_import import (
    BATCH_STATUS_UPLOADED,
    SOURCE_TYPE_HR_CONTROL_LIST,
)

CONTROL_LIST_FILENAME_RE = re.compile(
    r"^контрольный(?P<yymm>\d{4})\.(?P<ext>xlsx|xlsm)$",
    re.IGNORECASE,
)


class ControlListFilenameError(ValueError):
    """Raised when uploaded filename does not match control list naming rules."""


@dataclass(frozen=True)
class ParsedControlListFilename:
    original_filename: str
    yymm: str
    report_month: date
    suffix: str


def hr_import_storage_root() -> Path:
    configured = env("HR_IMPORT_STORAGE_DIR")
    if configured:
        return Path(configured)
    return PROJECT_ROOT / "runtime" / "hr-import"


def parse_control_list_filename(filename: str) -> ParsedControlListFilename:
    name = (filename or "").strip()
    match = CONTROL_LIST_FILENAME_RE.match(name)
    if not match:
        raise ControlListFilenameError(
            "Ожидается имя файла контрольныйYYMM.xlsx, например контрольный2606.xlsx."
        )
    yymm = match.group("yymm")
    month = int(yymm[2:])
    if month < 1 or month > 12:
        raise ControlListFilenameError(f"Некорректный месяц в имени файла: {yymm}.")
    year = 2000 + int(yymm[:2])
    ext = match.group("ext").lower()
    return ParsedControlListFilename(
        original_filename=name,
        yymm=yymm,
        report_month=date(year, month, 1),
        suffix=f".{ext}",
    )


def format_report_period(report_month: date) -> str:
    return f"{report_month.month:02d}.{report_month.year}"


def is_legacy_import_code(import_code: str) -> bool:
    return str(import_code or "").startswith("legacy-")


def build_technical_filename(import_code: str, suffix: str) -> str:
    return f"control-list-{import_code}{suffix}"


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def allocate_import_code(conn: Connection, yymm: str) -> str:
    row = conn.execute(
        text(
            """
            SELECT COALESCE(
                MAX(
                    CASE
                        WHEN import_code ~ '^[0-9]{4}-[0-9]{2}$'
                        THEN CAST(SPLIT_PART(import_code, '-', 2) AS INTEGER)
                    END
                ),
                0
            ) AS max_seq
            FROM public.hr_import_batches
            WHERE import_code LIKE :prefix
            """
        ),
        {"prefix": f"{yymm}-%"},
    ).mappings().one()
    seq = int(row["max_seq"]) + 1
    return f"{yymm}-{seq:02d}"


def _insert_source_file(
    conn: Connection,
    *,
    content: bytes,
    parsed: ParsedControlListFilename,
    import_code: str,
    imported_by: int,
    imported_at: datetime,
    source_last_modified_at: Optional[datetime],
) -> tuple[int, str]:
    technical_filename = build_technical_filename(import_code, parsed.suffix)
    storage_root = hr_import_storage_root()
    storage_root.mkdir(parents=True, exist_ok=True)
    dest_path = storage_root / technical_filename
    if dest_path.exists():
        raise RuntimeError(f"Storage collision: {dest_path}")
    dest_path.write_bytes(content)
    storage_ref = str(dest_path.resolve())
    source_file_id = conn.execute(
        text(
            """
            INSERT INTO public.hr_source_files (
                content_sha256,
                original_filename,
                technical_filename,
                report_month,
                source_system,
                byte_size,
                storage_ref,
                uploaded_by_user_id,
                uploaded_at,
                source_last_modified_at
            )
            VALUES (
                :content_sha256,
                :original_filename,
                :technical_filename,
                :report_month,
                :source_system,
                :byte_size,
                :storage_ref,
                :uploaded_by_user_id,
                :uploaded_at,
                :source_last_modified_at
            )
            RETURNING source_file_id
            """
        ),
        {
            "content_sha256": sha256_hex(content),
            "original_filename": parsed.original_filename,
            "technical_filename": technical_filename,
            "report_month": parsed.report_month,
            "source_system": SOURCE_TYPE_HR_CONTROL_LIST,
            "byte_size": len(content),
            "storage_ref": storage_ref,
            "uploaded_by_user_id": imported_by,
            "uploaded_at": imported_at,
            "source_last_modified_at": source_last_modified_at,
        },
    ).scalar_one()
    return int(source_file_id), storage_ref


def create_control_list_batch(
    conn: Connection,
    *,
    content: bytes,
    original_filename: str,
    imported_by: int,
    imported_at: Optional[datetime] = None,
    source_last_modified_at: Optional[datetime] = None,
    source_type: str = SOURCE_TYPE_HR_CONTROL_LIST,
) -> tuple[int, str, int]:
    """Create batch + persisted source file. Returns (batch_id, import_code, source_file_id)."""
    parsed = parse_control_list_filename(original_filename)
    at = imported_at or datetime.now(timezone.utc)
    import_code = allocate_import_code(conn, parsed.yymm)
    storage_ref: Optional[str] = None
    source_file_id: Optional[int] = None
    try:
        source_file_id, storage_ref = _insert_source_file(
            conn,
            content=content,
            parsed=parsed,
            import_code=import_code,
            imported_by=imported_by,
            imported_at=at,
            source_last_modified_at=source_last_modified_at,
        )
        batch_id = conn.execute(
        text(
            """
            INSERT INTO public.hr_import_batches (
                source_type,
                file_name,
                import_code,
                imported_by,
                imported_at,
                status,
                total_rows,
                valid_rows,
                error_rows,
                source_file_id
            )
            VALUES (
                :source_type,
                :file_name,
                :import_code,
                :imported_by,
                :imported_at,
                :status,
                0,
                0,
                0,
                :source_file_id
            )
            RETURNING batch_id
            """
        ),
        {
            "source_type": source_type,
            "file_name": parsed.original_filename,
            "import_code": import_code,
            "imported_by": imported_by,
            "imported_at": at,
            "status": BATCH_STATUS_UPLOADED,
            "source_file_id": source_file_id,
        },
        ).scalar_one()
        return int(batch_id), import_code, int(source_file_id)
    except Exception:
        if storage_ref:
            remove_stored_control_list_file(storage_ref)
        if source_file_id is not None:
            conn.execute(
                text("DELETE FROM public.hr_source_files WHERE source_file_id = :source_file_id"),
                {"source_file_id": source_file_id},
            )
        raise


def cleanup_failed_control_list_batch(
    conn: Connection,
    *,
    batch_id: Optional[int],
    source_file_id: Optional[int],
    storage_ref: Optional[str],
) -> None:
    if batch_id is not None:
        conn.execute(
            text("DELETE FROM public.hr_import_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        )
    if source_file_id is not None:
        conn.execute(
            text("DELETE FROM public.hr_source_files WHERE source_file_id = :source_file_id"),
            {"source_file_id": source_file_id},
        )
    if storage_ref:
        remove_stored_control_list_file(storage_ref)


def remove_stored_control_list_file(storage_ref: str) -> None:
    path = Path(storage_ref)
    if path.is_file():
        path.unlink()


def serialize_batch_file_metadata(row: dict[str, Any]) -> dict[str, Any]:
    report_month = row.get("report_month")
    report_period = format_report_period(report_month) if report_month else None
    source_modified = row.get("source_last_modified_at")
    imported_at = row.get("imported_at")
    return {
        "batch_id": int(row["batch_id"]),
        "import_code": row.get("import_code") or f"legacy-{row['batch_id']}",
        "file_name": row.get("file_name") or row.get("original_filename") or "",
        "original_filename": row.get("original_filename") or row.get("file_name") or "",
        "technical_filename": row.get("technical_filename"),
        "storage_ref": row.get("storage_ref"),
        "byte_size": int(row["byte_size"]) if row.get("byte_size") is not None else None,
        "content_sha256": row.get("content_sha256"),
        "report_month": report_month.isoformat() if report_month else None,
        "report_period": report_period,
        "source_last_modified_at": source_modified.isoformat() if source_modified else None,
        "imported_at": imported_at.isoformat() if imported_at else None,
        "status": row.get("status"),
        "total_rows": int(row.get("total_rows") or 0),
        "valid_rows": int(row.get("valid_rows") or 0),
        "error_rows": int(row.get("error_rows") or 0),
    }
