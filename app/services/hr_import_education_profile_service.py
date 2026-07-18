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
from app.services.hr_import_profile_override_service import (
    apply_profile_override,
    is_section_override,
    prepare_profile_override_for_storage,
)
from app.services.employee_import_profile_override_service import (
    load_employee_override,
    resolve_directory_employee_id,
    upsert_employee_override,
)
from app.services.hr_import_profile_service import build_import_profile

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


def _load_effective_profile_meta(
    conn: Connection,
    batch_id: int,
    row_id: int,
    *,
    employee_id: Optional[int] = None,
    payload: Optional[dict[str, Any]] = None,
    row_employee_id: Optional[int] = None,
) -> dict[str, Any]:
    """Row meta merged with employee-level override when directory employee is known."""
    meta = _load_profile_meta(conn, batch_id, row_id)
    resolved_id = employee_id
    if resolved_id is None:
        resolved_id = resolve_directory_employee_id(
            conn,
            row_employee_id=row_employee_id,
            payload=payload,
        )
    if resolved_id is not None:
        employee_meta = load_employee_override(conn, resolved_id)
        if employee_meta is not None:
            return employee_meta
    return meta


def _resolve_merged_profile(payload: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    base = build_import_profile(payload)
    override = meta.get("profile_override")
    if override and isinstance(override, dict):
        if is_section_override(override):
            profile = apply_profile_override(base, override)
        else:
            profile = _deep_merge(base, override)
    else:
        profile = base
    if "notes" not in (override or {}) and not profile.get("notes_raw"):
        profile["notes_raw"] = str(payload.get("note_raw", "") or "")
    profile["status"] = meta["profile_status"]
    profile["review_status"] = meta["profile_review_status"]
    return profile


def _resolve_group_employee_id(conn: Connection, group: dict[str, Any]) -> Optional[int]:
    primary = group["primary"]
    staging = primary["staging"]
    payload = primary["payload"]
    return resolve_directory_employee_id(
        conn,
        row_employee_id=staging.get("employee_id"),
        payload=payload,
    )


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


def _join_nonempty(parts: list[Any], sep: str = ", ") -> str:
    return sep.join(str(part).strip() for part in parts if str(part or "").strip())


def _preview_education_record(record: dict[str, Any]) -> dict[str, str]:
    text = _join_nonempty(
        [
            record.get("institution"),
            record.get("specialty"),
            record.get("completed_at"),
        ]
    )
    if not text:
        text = str(record.get("source_text") or "").strip()
    return {"text": text}


def _preview_training_record(record: dict[str, Any]) -> dict[str, str]:
    title = str(record.get("title") or record.get("source_text") or "").strip()
    parts = [title]
    organization = str(record.get("organization") or "").strip()
    if organization:
        parts.append(organization)
    hours = record.get("hours")
    if hours not in (None, ""):
        parts.append(f"{hours} ч")
    completed_at = str(record.get("completed_at") or record.get("started_at") or "").strip()
    if completed_at:
        parts.append(completed_at)
    return {"text": _join_nonempty(parts)}


def _preview_certificate_record(record: dict[str, Any]) -> dict[str, str]:
    topic = str(record.get("topic") or record.get("specialty") or "").strip()
    parts = [topic]
    number = str(record.get("certificate_number") or "").strip()
    if number:
        parts.append(f"№ {number}")
    issued_at = str(record.get("issued_at") or "").strip()
    if issued_at:
        parts.append(f"выдан {issued_at}")
    valid_until = str(record.get("valid_until") or "").strip()
    if valid_until:
        parts.append(f"до {valid_until}")
    if not any(parts):
        parts = [str(record.get("source_text") or "").strip()]
    return {"text": _join_nonempty(parts)}


def _preview_category_record(record: dict[str, Any]) -> dict[str, str]:
    text = _join_nonempty(
        [
            record.get("category"),
            record.get("specialty"),
            record.get("issued_at"),
        ]
    )
    if not text:
        text = str(record.get("source_text") or "").strip()
    return {"text": text}


def _serialize_portfolio_column(
    records: list[dict[str, Any]],
    preview_fn,
    *,
    preview_limit: int = 2,
) -> dict[str, Any]:
    previews = [preview_fn(record) for record in records[:preview_limit] if preview_fn(record).get("text")]
    extra_count = max(0, len(records) - len(previews))
    return {
        "count": len(records),
        "items": previews,
        "extra_count": extra_count,
    }


def _portfolio_counts(profile: dict[str, Any]) -> dict[str, int]:
    totals = profile.get("portfolio_totals") or {}
    return {
        "education": int(totals.get("education", len(profile.get("education_records") or []))),
        "training": int(totals.get("training", len(profile.get("training_records") or []))),
        "certificates": int(totals.get("certificates", len(profile.get("certificate_records") or []))),
        "categories": int(totals.get("categories", len(profile.get("category_records") or []))),
    }


def _serialize_portfolio_previews(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "education": _serialize_portfolio_column(
            profile.get("education_records") or [],
            _preview_education_record,
        ),
        "training": _serialize_portfolio_column(
            profile.get("training_records") or [],
            _preview_training_record,
        ),
        "certificates": _serialize_portfolio_column(
            profile.get("certificate_records") or [],
            _preview_certificate_record,
        ),
        "categories": _serialize_portfolio_column(
            profile.get("category_records") or [],
            _preview_category_record,
        ),
    }


def _aggregate_has_portfolio_content(group: dict[str, Any], content_filter: Optional[str]) -> bool:
    if not content_filter:
        return True
    counts = _portfolio_counts(group["merged_profile"])
    if content_filter == "education":
        return counts["education"] > 0
    if content_filter == "training":
        return counts["training"] > 0
    if content_filter == "certificates":
        return counts["certificates"] > 0
    if content_filter == "categories":
        return counts["categories"] > 0
    if content_filter == "empty":
        return all(value == 0 for value in counts.values())
    return True


def _build_portfolio_summary(aggregates: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "total": len(aggregates),
        "with_education": 0,
        "with_training": 0,
        "with_certificates": 0,
        "with_categories": 0,
        "without_portfolio": 0,
    }
    for group in aggregates:
        counts = _portfolio_counts(group["merged_profile"])
        has_any = False
        if counts["education"] > 0:
            summary["with_education"] += 1
            has_any = True
        if counts["training"] > 0:
            summary["with_training"] += 1
            has_any = True
        if counts["certificates"] > 0:
            summary["with_certificates"] += 1
            has_any = True
        if counts["categories"] > 0:
            summary["with_categories"] += 1
            has_any = True
        if not has_any:
            summary["without_portfolio"] += 1
    return summary


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
        meta = _load_effective_profile_meta(
            conn,
            batch_id,
            row["row_id"],
            payload=payload,
            row_employee_id=staging.get("employee_id"),
        )
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
    from app.medical_org_groups import enrich_effective_log_group_fields

    primary = group["primary"]
    payload = primary["payload"]
    recoding = primary["recoding"]
    profile = group["merged_profile"]
    totals = profile.get("portfolio_totals") or {}
    portfolio = _serialize_portfolio_previews(profile)
    iin = str(payload.get("iin", "") or "").strip()
    review_status = group["review_status"]
    summary = {
        "profile_id": group["primary_row_id"],
        "aggregate_key": group["identity_key"],
        "batch_id": batch_id,
        "row_id": group["primary_row_id"],
        "source_row_ids": group["source_row_ids"],
        "employee_id": primary["staging"].get("employee_id"),
        "full_name": str(payload.get("full_name", "") or ""),
        "iin": iin,
        "department_source": str(payload.get("department", "") or ""),
        "org_unit_id": int(recoding["org_unit_id"]) if recoding and recoding.get("org_unit_id") else None,
        "org_unit_name": recoding["org_unit_name"] if recoding else "",
        "org_group_id": primary["row"].get("org_group_id"),
        "department_group": recoding["department_group"] if recoding else "",
        "position_raw": str(payload.get("position_raw", "") or ""),
        "education_count": int(totals.get("education", 0)),
        "training_count": int(totals.get("training", 0)),
        "certificate_count": int(totals.get("certificates", 0)),
        "category_count": int(totals.get("categories", 0)),
        "award_count": int(totals.get("awards", 0)),
        "education": portfolio["education"],
        "training": portfolio["training"],
        "certificates": portfolio["certificates"],
        "categories": portfolio["categories"],
        "profile_status": group["profile_status"],
        "review_status": review_status,
        "review_status_label": REVIEW_STATUS_LABELS.get(review_status, review_status),
    }
    return enrich_effective_log_group_fields(summary)


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
        "iin": iin,
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
    org_group_id: Optional[int] = None,
    effective_log_group: Optional[str] = None,
    org_unit_id: Optional[int] = None,
    org_unit_name: Optional[str] = None,
    q_name: Optional[str] = None,
    content_filter: Optional[str] = None,
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

    from app.medical_org_groups import enrich_effective_log_group_fields, resolve_group_id_from_filter

    effective_org_group_id = resolve_group_id_from_filter(
        org_group_id=org_group_id,
        effective_log_group=effective_log_group or department_group,
        department_group=department_group,
    )

    if effective_org_group_id is not None:
        rows = [r for r in rows if r.get("org_group_id") == effective_org_group_id]
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
    portfolio_summary = _build_portfolio_summary(aggregates)
    if content_filter:
        aggregates = [
            group for group in aggregates if _aggregate_has_portfolio_content(group, content_filter)
        ]
    total = len(aggregates)
    page = aggregates[offset : offset + limit]
    items = [_serialize_profile_summary(group, batch_id=batch_id) for group in page]
    return {
        "batch_id": batch_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "summary": portfolio_summary,
        "items": items,
    }


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
    updated_by: Optional[int] = None,
) -> dict[str, Any]:
    if not _profile_columns_available(conn):
        raise BatchNotFoundError("profile staging columns not available — run alembic upgrade head")
    _ensure_batch_exists(conn, batch_id)
    group = _find_aggregate(conn, batch_id, profile_id)
    if review_status is not None and review_status not in REVIEW_STATUS_LABELS:
        raise ValueError(f"invalid review_status: {review_status}")
    if profile_status is not None and profile_status not in (PROFILE_STATUS_ACTIVE, PROFILE_STATUS_ARCHIVED):
        raise ValueError(f"invalid profile_status: {profile_status}")
    stored_profile = prepare_profile_override_for_storage(profile) if profile is not None else None
    _apply_to_aggregate_rows(
        conn,
        batch_id,
        group,
        profile=stored_profile,
        review_status=review_status,
        profile_status=profile_status,
    )
    resolved_employee_id = _resolve_group_employee_id(conn, group)
    if stored_profile is not None and resolved_employee_id is not None:
        batch_row = conn.execute(
            text(
                """
                SELECT imported_at
                FROM public.hr_import_batches
                WHERE batch_id = :batch_id
                """
            ),
            {"batch_id": batch_id},
        ).first()
        base_imported_at = batch_row[0] if batch_row else None
        upsert_employee_override(
            conn,
            resolved_employee_id,
            profile=stored_profile,
            profile_status=profile_status,
            review_status=review_status,
            updated_by=updated_by,
            base_batch_id=batch_id,
            base_row_id=int(group["primary_row_id"]),
            base_imported_at=base_imported_at,
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
