"""Employee education profiles from HR import staging (Phase 2F.3)."""
from __future__ import annotations

import copy
import re
from collections import defaultdict
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

_EDUCATION_TYPE_KEYS = ("basic", "internship", "residency", "masters", "phd")


def _norm_token(value: str) -> str:
    text_val = (value or "").strip().lower().replace("ё", "е")
    return " ".join(text_val.split())


def _employee_identity_key(row: dict[str, Any], payload: dict[str, Any]) -> str:
    """Dedup key: valid IIN, else normalized name + canonical dept + position."""
    iin = re.sub(r"\D", "", str(payload.get("iin", "") or ""))
    if len(iin) == 12:
        return f"iin:{iin}"
    name = _norm_token(str(payload.get("full_name", "") or ""))
    canonical = _norm_token(str(row.get("org_unit_name") or payload.get("department", "") or ""))
    position = _norm_token(str(payload.get("position_raw", "") or ""))
    return f"name:{name}|dept:{canonical}|pos:{position}"


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


def _record_dedupe_key(record: dict[str, Any], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_norm_token(str(record.get(field, "") or "")) for field in fields)


def _dedupe_records(records: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    result: list[dict[str, Any]] = []
    for idx, record in enumerate(records):
        key = _record_dedupe_key(record, fields)
        if not any(key):
            key = ("__fallback__", str(idx), _norm_token(str(record.get("source_text", "") or "")))
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result


def _recompute_portfolio_totals(profile: dict[str, Any]) -> None:
    profile["portfolio_totals"] = {
        "education": len(profile.get("education_records") or []),
        "training": len(profile.get("training_records") or []),
        "categories": len(profile.get("category_records") or []),
        "certificates": len(profile.get("certificate_records") or []),
        "awards": len(profile.get("award_records") or []),
        "degrees": len((profile.get("degrees") or {}).get("records") or []),
    }


def _merge_profiles(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    if not profiles:
        return {}
    merged = copy.deepcopy(profiles[0])
    for profile in profiles[1:]:
        for key in (
            "education_records",
            "training_records",
            "category_records",
            "certificate_records",
            "award_records",
        ):
            merged.setdefault(key, [])
            merged[key].extend(profile.get(key) or [])
        education = profile.get("education") or {}
        merged.setdefault("education", {})
        for edu_type in _EDUCATION_TYPE_KEYS:
            merged["education"].setdefault(edu_type, [])
            merged["education"][edu_type].extend(education.get(edu_type) or [])
        degrees = profile.get("degrees") or {}
        merged_degrees = merged.setdefault("degrees", {"records": []})
        merged_degrees.setdefault("records", [])
        merged_degrees["records"].extend(degrees.get("records") or [])
        merged_degrees["candidate_medical_sciences"] = bool(
            merged_degrees.get("candidate_medical_sciences")
            or degrees.get("candidate_medical_sciences")
        )
        merged_degrees["doctor_medical_sciences"] = bool(
            merged_degrees.get("doctor_medical_sciences")
            or degrees.get("doctor_medical_sciences")
        )
        if degrees.get("raw_text") and degrees["raw_text"] not in (merged_degrees.get("raw_text") or ""):
            merged_degrees["raw_text"] = "; ".join(
                filter(None, [merged_degrees.get("raw_text"), degrees.get("raw_text")])
            )
        note = profile.get("notes_raw") or ""
        if note and note not in (merged.get("notes_raw") or ""):
            merged["notes_raw"] = "; ".join(filter(None, [merged.get("notes_raw"), note]))

    merged["education_records"] = _dedupe_records(
        merged.get("education_records") or [], ("institution", "completed_at", "specialty")
    )
    merged["training_records"] = _dedupe_records(
        merged.get("training_records") or [], ("title", "completed_at", "hours")
    )
    merged["category_records"] = _dedupe_records(
        merged.get("category_records") or [], ("category", "issued_at", "specialty")
    )
    merged["certificate_records"] = _dedupe_records(
        merged.get("certificate_records") or [], ("kind", "topic", "issued_at", "specialty")
    )
    merged["award_records"] = _dedupe_records(
        merged.get("award_records") or [], ("title", "date")
    )
    _recompute_portfolio_totals(merged)
    return merged


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


def _build_group_members(
    conn: Connection,
    batch_id: int,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        staging = load_row_payload(conn, batch_id, row["row_id"])
        payload = staging["payload"]
        identity_key = _employee_identity_key(row, payload)
        meta = _load_profile_meta(conn, batch_id, row["row_id"])
        recoding = lookup_recoding(conn, str(row.get("department") or ""))
        profile = _resolve_merged_profile(payload, meta)
        grouped[identity_key].append(
            {
                "row_id": row["row_id"],
                "row": row,
                "staging": staging,
                "payload": payload,
                "meta": meta,
                "recoding": recoding,
                "profile": profile,
                "identity_key": identity_key,
            }
        )

    aggregates: list[dict[str, Any]] = []
    for identity_key, members in grouped.items():
        members.sort(key=lambda m: m["row_id"])
        primary = members[0]
        merged_profile = _merge_profiles([m["profile"] for m in members])
        review_status = primary["meta"]["profile_review_status"]
        if any(m["meta"]["profile_review_status"] == REVIEW_STATUS_NEEDS_ATTENTION for m in members):
            review_status = REVIEW_STATUS_NEEDS_ATTENTION
        elif all(m["meta"]["profile_review_status"] == REVIEW_STATUS_REVIEWED for m in members):
            review_status = REVIEW_STATUS_REVIEWED
        aggregates.append(
            {
                "identity_key": identity_key,
                "primary_row_id": primary["row_id"],
                "source_row_ids": [m["row_id"] for m in members],
                "primary": primary,
                "members": members,
                "merged_profile": merged_profile,
                "review_status": review_status,
                "profile_status": primary["meta"]["profile_status"],
            }
        )
    aggregates.sort(key=lambda g: (g["primary"]["payload"].get("full_name", ""), g["primary_row_id"]))
    return aggregates


def _find_aggregate(conn: Connection, batch_id: int, profile_id: int) -> dict[str, Any]:
    rows = _load_employee_rows(conn, batch_id)
    aggregates = _build_group_members(conn, batch_id, rows)
    for group in aggregates:
        if profile_id in group["source_row_ids"]:
            return group
    raise BatchNotFoundError(f"profile_id={profile_id} not found in batch {batch_id}")


def _serialize_profile_summary(group: dict[str, Any], *, batch_id: int) -> dict[str, Any]:
    primary = group["primary"]
    payload = primary["payload"]
    recoding = primary["recoding"]
    profile = group["merged_profile"]
    totals = profile.get("portfolio_totals") or {}
    iin = str(payload.get("iin", "") or "").strip()
    review_status = group["review_status"]
    return {
        "profile_id": group["primary_row_id"],
        "aggregate_key": group["identity_key"],
        "batch_id": batch_id,
        "row_id": group["primary_row_id"],
        "source_row_ids": group["source_row_ids"],
        "employee_id": primary["staging"].get("employee_id"),
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
        "profile_status": group["profile_status"],
        "review_status": review_status,
        "review_status_label": REVIEW_STATUS_LABELS.get(review_status, review_status),
    }


def _serialize_profile_detail(group: dict[str, Any], *, batch_id: int) -> dict[str, Any]:
    primary = group["primary"]
    payload = primary["payload"]
    recoding = primary["recoding"]
    profile = copy.deepcopy(group["merged_profile"])
    iin = str(payload.get("iin", "") or "").strip()
    review_status = group["review_status"]
    profile["status"] = group["profile_status"]
    profile["review_status"] = review_status
    return {
        "profile_id": group["primary_row_id"],
        "aggregate_key": group["identity_key"],
        "batch_id": batch_id,
        "row_id": group["primary_row_id"],
        "source_row_ids": group["source_row_ids"],
        "employee_id": primary["staging"].get("employee_id"),
        "source_sheet": primary["staging"]["source_sheet"],
        "source_row_number": primary["staging"]["source_row_number"],
        "full_name": str(payload.get("full_name", "") or ""),
        "iin_masked": mask_iin(iin) if iin else "",
        "profile_status": group["profile_status"],
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


def list_education_profiles(
    conn: Connection,
    batch_id: int,
    *,
    department_group: Optional[str] = None,
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

    if department_group:
        rows = [r for r in rows if r.get("department_group") == department_group]
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

    aggregates = _build_group_members(conn, batch_id, rows)
    total = len(aggregates)
    page = aggregates[offset : offset + limit]
    items = [_serialize_profile_summary(group, batch_id=batch_id) for group in page]
    return {"batch_id": batch_id, "total": total, "limit": limit, "offset": offset, "items": items}


def get_education_profile(conn: Connection, batch_id: int, profile_id: int) -> dict[str, Any]:
    group = _find_aggregate(conn, batch_id, profile_id)
    return _serialize_profile_detail(group, batch_id=batch_id)


def _apply_to_aggregate_rows(
    conn: Connection,
    batch_id: int,
    group: dict[str, Any],
    *,
    profile: Optional[dict[str, Any]] = None,
    review_status: Optional[str] = None,
    profile_status: Optional[str] = None,
) -> None:
    primary_row_id = group["primary_row_id"]
    for member in group["members"]:
        row_id = member["row_id"]
        sets: list[str] = []
        params: dict[str, Any] = {"batch_id": batch_id, "row_id": row_id}
        if profile is not None and row_id == primary_row_id:
            import json

            sets.append("profile_override = CAST(:profile_override AS JSONB)")
            params["profile_override"] = json.dumps(profile, ensure_ascii=False)
        if review_status is not None:
            sets.append("profile_review_status = :profile_review_status")
            params["profile_review_status"] = review_status
        if profile_status is not None:
            sets.append("profile_status = :profile_status")
            params["profile_status"] = profile_status
        if not sets:
            continue
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
    group = _find_aggregate(conn, batch_id, profile_id)
    if review_status is not None and review_status not in REVIEW_STATUS_LABELS:
        raise ValueError(f"invalid review_status: {review_status}")
    if profile_status is not None and profile_status not in (PROFILE_STATUS_ACTIVE, PROFILE_STATUS_ARCHIVED):
        raise ValueError(f"invalid profile_status: {profile_status}")
    _apply_to_aggregate_rows(
        conn,
        batch_id,
        group,
        profile=profile,
        review_status=review_status,
        profile_status=profile_status,
    )
    return get_education_profile(conn, batch_id, group["primary_row_id"])


def archive_education_profile(conn: Connection, batch_id: int, profile_id: int) -> dict[str, Any]:
    """Staging-only archive — does not affect employees or HR events."""
    return update_education_profile(
        conn,
        batch_id,
        profile_id,
        profile_status=PROFILE_STATUS_ARCHIVED,
    )
