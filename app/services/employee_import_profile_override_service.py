"""Employee-level HR import profile overrides — ADR-038 Phase A / A.1."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.hr_import_profile_override_service import prepare_profile_override_for_storage

logger = logging.getLogger(__name__)

_PROFILE_STATUS_ACTIVE = "active"
_REVIEW_STATUS_PENDING = "pending"


def _table_exists(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'employee_import_profile_overrides'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def _provenance_columns_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'employee_import_profile_overrides'
              AND column_name = 'base_batch_id'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def _norm_name(value: str) -> str:
    text_val = (value or "").strip().lower().replace("ё", "е")
    return " ".join(text_val.split())


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _parse_jsonb(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _iso_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def resolve_directory_employee_id(
    conn: Connection,
    *,
    row_employee_id: Optional[int] = None,
    payload: Optional[dict[str, Any]] = None,
) -> Optional[int]:
    """Resolve directory employee_id from staging row link or import payload.

    Returns None when name or IIN matching is ambiguous — caller must keep row-level override only.
    """
    if row_employee_id:
        return int(row_employee_id)
    if not payload:
        return None

    iin_digits = _digits_only(str(payload.get("iin", "") or ""))
    if len(iin_digits) == 12:
        rows = conn.execute(
            text(
                """
                SELECT DISTINCT ei.employee_id
                FROM public.employee_identities ei
                WHERE ei.identity_type = 'IIN'
                  AND ei.valid_to IS NULL
                  AND regexp_replace(COALESCE(ei.identity_value, ''), '[^0-9]', '', 'g') = :iin
                ORDER BY ei.employee_id
                """
            ),
            {"iin": iin_digits},
        ).fetchall()
        employee_ids = [int(row[0]) for row in rows if row and row[0]]
        if len(employee_ids) > 1:
            logger.warning(
                "resolve_directory_employee_id: ambiguous IIN match iin=%s candidates=%s",
                iin_digits,
                employee_ids,
            )
            return None
        if len(employee_ids) == 1:
            return employee_ids[0]

    full_name = str(payload.get("full_name", "") or "").strip()
    if not full_name:
        return None
    norm_name = _norm_name(full_name)
    rows = conn.execute(
        text(
            """
            SELECT employee_id
            FROM public.employees
            WHERE lower(replace(trim(full_name), 'ё', 'е')) = :norm_name
            ORDER BY employee_id
            """
        ),
        {"norm_name": norm_name},
    ).fetchall()
    employee_ids = [int(row[0]) for row in rows if row and row[0]]
    if len(employee_ids) > 1:
        logger.warning(
            "resolve_directory_employee_id: ambiguous full_name match name=%r candidates=%s",
            full_name,
            employee_ids,
        )
        return None
    if len(employee_ids) == 1:
        return employee_ids[0]
    return None


def load_employee_override(conn: Connection, employee_id: int) -> Optional[dict[str, Any]]:
    if not _table_exists(conn):
        return None
    if _provenance_columns_available(conn):
        row = conn.execute(
            text(
                """
                SELECT
                    profile_override,
                    profile_status,
                    profile_review_status,
                    base_batch_id,
                    base_row_id,
                    base_imported_at,
                    created_by,
                    updated_by,
                    created_at,
                    updated_at
                FROM public.employee_import_profile_overrides
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": employee_id},
        ).mappings().first()
    else:
        row = conn.execute(
            text(
                """
                SELECT profile_override, profile_status, profile_review_status, updated_by
                FROM public.employee_import_profile_overrides
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": employee_id},
        ).mappings().first()
    if not row:
        return None
    override = _parse_jsonb(row["profile_override"])
    result: dict[str, Any] = {
        "profile_override": override,
        "profile_status": row["profile_status"] or _PROFILE_STATUS_ACTIVE,
        "profile_review_status": row["profile_review_status"] or _REVIEW_STATUS_PENDING,
        "updated_by": int(row["updated_by"]) if row.get("updated_by") else None,
    }
    if _provenance_columns_available(conn):
        result.update(
            {
                "base_batch_id": int(row["base_batch_id"]) if row.get("base_batch_id") else None,
                "base_row_id": int(row["base_row_id"]) if row.get("base_row_id") else None,
                "base_imported_at": _iso_datetime(row.get("base_imported_at")),
                "created_by": int(row["created_by"]) if row.get("created_by") else None,
                "created_at": _iso_datetime(row.get("created_at")),
                "updated_at": _iso_datetime(row.get("updated_at")),
            }
        )
    return result


def upsert_employee_override(
    conn: Connection,
    employee_id: int,
    *,
    profile: dict[str, Any],
    profile_status: Optional[str] = None,
    review_status: Optional[str] = None,
    updated_by: Optional[int] = None,
    base_batch_id: Optional[int] = None,
    base_row_id: Optional[int] = None,
    base_imported_at: Optional[datetime] = None,
) -> dict[str, Any]:
    if not _table_exists(conn):
        raise RuntimeError(
            "employee_import_profile_overrides not available — run alembic upgrade head"
        )
    override = prepare_profile_override_for_storage(profile)
    status = profile_status or _PROFILE_STATUS_ACTIVE
    review = review_status or _REVIEW_STATUS_PENDING
    if _provenance_columns_available(conn):
        conn.execute(
            text(
                """
                INSERT INTO public.employee_import_profile_overrides (
                    employee_id,
                    profile_override,
                    profile_status,
                    profile_review_status,
                    base_batch_id,
                    base_row_id,
                    base_imported_at,
                    created_by,
                    updated_by,
                    created_at,
                    updated_at
                )
                VALUES (
                    :employee_id,
                    CAST(:profile_override AS JSONB),
                    :profile_status,
                    :profile_review_status,
                    :base_batch_id,
                    :base_row_id,
                    :base_imported_at,
                    :created_by,
                    :updated_by,
                    NOW(),
                    NOW()
                )
                ON CONFLICT (employee_id) DO UPDATE SET
                    profile_override = EXCLUDED.profile_override,
                    profile_status = EXCLUDED.profile_status,
                    profile_review_status = EXCLUDED.profile_review_status,
                    base_batch_id = EXCLUDED.base_batch_id,
                    base_row_id = EXCLUDED.base_row_id,
                    base_imported_at = EXCLUDED.base_imported_at,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = NOW(),
                    created_by = COALESCE(
                        public.employee_import_profile_overrides.created_by,
                        EXCLUDED.created_by
                    )
                """
            ),
            {
                "employee_id": employee_id,
                "profile_override": json.dumps(override, ensure_ascii=False),
                "profile_status": status,
                "profile_review_status": review,
                "base_batch_id": base_batch_id,
                "base_row_id": base_row_id,
                "base_imported_at": base_imported_at,
                "created_by": updated_by,
                "updated_by": updated_by,
            },
        )
    else:
        conn.execute(
            text(
                """
                INSERT INTO public.employee_import_profile_overrides (
                    employee_id,
                    profile_override,
                    profile_status,
                    profile_review_status,
                    updated_by,
                    created_at,
                    updated_at
                )
                VALUES (
                    :employee_id,
                    CAST(:profile_override AS JSONB),
                    :profile_status,
                    :profile_review_status,
                    :updated_by,
                    NOW(),
                    NOW()
                )
                ON CONFLICT (employee_id) DO UPDATE SET
                    profile_override = EXCLUDED.profile_override,
                    profile_status = EXCLUDED.profile_status,
                    profile_review_status = EXCLUDED.profile_review_status,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = NOW()
                """
            ),
            {
                "employee_id": employee_id,
                "profile_override": json.dumps(override, ensure_ascii=False),
                "profile_status": status,
                "profile_review_status": review,
                "updated_by": updated_by,
            },
        )
    result = load_employee_override(conn, employee_id)
    assert result is not None
    return result


def delete_employee_override(conn: Connection, employee_id: int) -> None:
    if not _table_exists(conn):
        return
    conn.execute(
        text(
            """
            DELETE FROM public.employee_import_profile_overrides
            WHERE employee_id = :employee_id
            """
        ),
        {"employee_id": employee_id},
    )


def employee_overrides_available(conn: Connection) -> bool:
    return _table_exists(conn)
