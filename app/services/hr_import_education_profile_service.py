"""Employee education profiles from HR import staging (Phase 2F.3)."""
from __future__ import annotations

import copy
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.department_recoding_service import lookup_recoding
from app.services.hr_import_analytics_service import (
    BatchNotFoundError,
    _ensure_batch_exists,
    is_real_employee_row,
    load_row_payload,
)
from app.services.hr_import_profile_service import build_import_profile
from scripts.import_hr_control_list import mask_iin

PROFILE_STATUS_ACTIVE = "active"
PROFILE_STATUS_ARCHIVED = "archived"

REVIEW_STATUS_PENDING = "pending"
REVIEW_STATUS_REVIEWED = "reviewed"
REVIEW_STATUS_NEEDS_ATTENTION = "needs_attention"

REVIEW_STATUS_LABELS = {
    REVIEW_STATUS_PENDING: "На проверке",
    REVIEW_STATUS_REVIEWED: "Проверено",
    REVIEW_STATUS_NEEDS_ATTENTION: "Требует внимания",
}


def _profile_columns_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'hr_import_rows'
              AND column_name = 'profile_override'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def _load_profile_meta(conn: Connection, batch_id: int, row_id: int) -> dict[str, Any]:
    if not _profile_columns_available(conn):
        return {
            "profile_override": None,
            "profile_status": PROFILE_STATUS_ACTIVE,
            "profile_review_status": REVIEW_STATUS_PENDING,
        }
    row = conn.execute(
        text(
            """
            SELECT profile_override, profile_status, profile_review_status
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id AND row_id = :row_id
            """
        ),
        {"batch_id": batch_id, "row_id": row_id},
    ).mappings().first()
    if not row:
        raise BatchNotFoundError(f"row_id={row_id} not found in batch {batch_id}")
    override = row["profile_override"]
    if isinstance(override, str):
        import json

        override = json.loads(override)
    return {
        "profile_override": override,
        "profile_status": row["profile_status"] or PROFILE_STATUS_ACTIVE,
        "profile_review_status": row["profile_review_status"] or REVIEW_STATUS_PENDING,
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _resolve_merged_profile(payload: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    base = build_import_profile(payload)
    override = meta.get("profile_override")
    if override and isinstance(override, dict):
        profile = _deep_merge(base, override)
    else:
        profile = base
    profile["notes_raw"] = str(payload.get("note_raw", "") or "")
    profile["status"] = meta["profile_status"]
    profile["review_status"] = meta["profile_review_status"]
    return profile


def _serialize_profile_summary(
    *,
    batch_id: int,
    row_id: int,
    payload: dict[str, Any],
    meta: dict[str, Any],
    recoding: Optional[dict[str, Any]],
    employee_id: Optional[int],
) -> dict[str, Any]:
    profile = _resolve_merged_profile(payload, meta)
    totals = profile.get("portfolio_totals") or {}
    iin = str(payload.get("iin", "") or "").strip()
    review_status = meta["profile_review_status"]
    return {
        "profile_id": row_id,
        "batch_id": batch_id,
        "row_id": row_id,
        "employee_id": employee_id,
        "full_name": str(payload.get("full_name", "") or ""),
        "iin_masked": mask_iin(iin) if iin else "",
        "department_source": str(payload.get("department", "") or ""),
        "org_unit_id": int(recoding["org_unit_id"]) if recoding and recoding.get("org_unit_id") else None,
        "org_unit_name": recoding["org_unit_name"] if recoding else "",
        "department_group": recoding["department_group"] if recoding else "",
        "position_raw": str(payload.get("position_raw", "") or ""),
        "education_count": int(totals.get("education", 0)),
        "training_count": int(totals.get("training", 0)),
        "certificate_count": int(totals.get("certificates", 0)),
        "category_count": int(totals.get("categories", 0)),
        "award_count": int(totals.get("awards", 0)),
        "profile_status": meta["profile_status"],
        "review_status": review_status,
        "review_status_label": REVIEW_STATUS_LABELS.get(review_status, review_status),
    }


def _serialize_profile_detail(
    *,
    batch_id: int,
    row: dict[str, Any],
    meta: dict[str, Any],
    recoding: Optional[dict[str, Any]],
) -> dict[str, Any]:
    payload = row["payload"]
    profile = _resolve_merged_profile(payload, meta)
    iin = str(payload.get("iin", "") or "").strip()
    review_status = meta["profile_review_status"]
    return {
        "profile_id": row["row_id"],
        "batch_id": batch_id,
        "row_id": row["row_id"],
        "employee_id": row.get("employee_id"),
        "source_sheet": row["source_sheet"],
        "source_row_number": row["source_row_number"],
        "full_name": str(payload.get("full_name", "") or ""),
        "iin_masked": mask_iin(iin) if iin else "",
        "profile_status": meta["profile_status"],
        "review_status": review_status,
        "review_status_label": REVIEW_STATUS_LABELS.get(review_status, review_status),
        "department_recoding": {
            "org_unit_id": int(recoding["org_unit_id"]) if recoding and recoding.get("org_unit_id") else None,
            "org_unit_name": recoding["org_unit_name"] if recoding else "",
            "department_group": recoding["department_group"] if recoding else "",
        }
        if recoding
        else None,
        "profile": profile,
    }


def _load_employee_rows(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    from app.services.hr_import_analytics_service import _load_staging_rows

    return [r for r in _load_staging_rows(conn, batch_id) if is_real_employee_row(r)]


def _matches_department_filter(
    row: dict[str, Any],
    *,
    org_unit_id: Optional[int],
    org_unit_name: Optional[str],
) -> bool:
    if org_unit_id is not None:
        if row.get("org_unit_id") == org_unit_id:
            return True
        if org_unit_name and (row.get("org_unit_name") or "").strip().lower() == org_unit_name.strip().lower():
            return True
        return False
    if org_unit_name:
        return (row.get("org_unit_name") or "").strip().lower() == org_unit_name.strip().lower()
    return True


def list_education_profiles(
    conn: Connection,
    batch_id: int,
    *,
    org_unit_id: Optional[int] = None,
    org_unit_name: Optional[str] = None,
    q_name: Optional[str] = None,
    include_archived: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    _ensure_batch_exists(conn, batch_id)
    rows = _load_employee_rows(conn, batch_id)
    if not include_archived and _profile_columns_available(conn):
        archived_ids = {
            int(r[0])
            for r in conn.execute(
                text(
                    """
                    SELECT row_id FROM public.hr_import_rows
                    WHERE batch_id = :batch_id AND profile_status = 'archived'
                    """
                ),
                {"batch_id": batch_id},
            ).fetchall()
        }
        rows = [r for r in rows if r["row_id"] not in archived_ids]

    if org_unit_id is not None or org_unit_name:
        rows = [
            r
            for r in rows
            if _matches_department_filter(
                r, org_unit_id=org_unit_id, org_unit_name=org_unit_name
            )
        ]
    if q_name:
        needle = q_name.strip().lower()
        rows = [r for r in rows if needle in r["full_name"].lower()]

    total = len(rows)
    page = rows[offset : offset + limit]
    items: list[dict[str, Any]] = []
    for row in page:
        staging = load_row_payload(conn, batch_id, row["row_id"])
        meta = _load_profile_meta(conn, batch_id, row["row_id"])
        recoding = lookup_recoding(conn, str(row.get("department") or ""))
        items.append(
            _serialize_profile_summary(
                batch_id=batch_id,
                row_id=row["row_id"],
                payload=staging["payload"],
                meta=meta,
                recoding=recoding,
                employee_id=staging.get("employee_id"),
            )
        )
    return {"batch_id": batch_id, "total": total, "limit": limit, "offset": offset, "items": items}


def get_education_profile(conn: Connection, batch_id: int, profile_id: int) -> dict[str, Any]:
    row = load_row_payload(conn, batch_id, profile_id)
    meta = _load_profile_meta(conn, batch_id, profile_id)
    department = str(row["payload"].get("department", "") or "")
    recoding = lookup_recoding(conn, department)
    return _serialize_profile_detail(
        batch_id=batch_id,
        row=row,
        meta=meta,
        recoding=recoding,
    )


def update_education_profile(
    conn: Connection,
    batch_id: int,
    profile_id: int,
    *,
    profile: Optional[dict[str, Any]] = None,
    review_status: Optional[str] = None,
    profile_status: Optional[str] = None,
) -> dict[str, Any]:
    if not _profile_columns_available(conn):
        raise BatchNotFoundError("profile staging columns not available — run alembic upgrade head")
    _ensure_batch_exists(conn, batch_id)
    load_row_payload(conn, batch_id, profile_id)
    sets: list[str] = []
    params: dict[str, Any] = {
        "batch_id": batch_id,
        "row_id": profile_id,
    }
    if profile is not None:
        import json

        sets.append("profile_override = CAST(:profile_override AS JSONB)")
        params["profile_override"] = json.dumps(profile, ensure_ascii=False)
    if review_status is not None:
        if review_status not in REVIEW_STATUS_LABELS:
            raise ValueError(f"invalid review_status: {review_status}")
        sets.append("profile_review_status = :profile_review_status")
        params["profile_review_status"] = review_status
    if profile_status is not None:
        if profile_status not in (PROFILE_STATUS_ACTIVE, PROFILE_STATUS_ARCHIVED):
            raise ValueError(f"invalid profile_status: {profile_status}")
        sets.append("profile_status = :profile_status")
        params["profile_status"] = profile_status

    if not sets:
        return get_education_profile(conn, batch_id, profile_id)

    conn.execute(
        text(
            f"""
            UPDATE public.hr_import_rows
            SET {", ".join(sets)}
            WHERE batch_id = :batch_id AND row_id = :row_id
            """
        ),
        params,
    )
    return get_education_profile(conn, batch_id, profile_id)


def archive_education_profile(conn: Connection, batch_id: int, profile_id: int) -> dict[str, Any]:
    """Staging-only archive — does not affect employees or HR events."""
    return update_education_profile(
        conn,
        batch_id,
        profile_id,
        profile_status=PROFILE_STATUS_ARCHIVED,
    )
