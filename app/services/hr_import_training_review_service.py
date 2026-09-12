"""Review workflow for imported training records, kept entirely in HR-import staging.

The normalized-record table already has a sparse ``review_override_json`` layer.
This module reserves the private ``_training_review_v1`` member of that JSON for
the training-review state, optimistic version, proposal and append-only history.
It deliberately never writes canonical PersonTraining data.
"""
from __future__ import annotations

import json
import math
import re
import hashlib
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.hr_import_normalized_record_service import (
    RECORD_KIND_TRAINING,
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_PENDING,
    REVIEW_STATUS_REJECTED,
    _effective_payload,
    _fetch_normalized_record_row,
    _parse_review_override_json,
    _parsed_payload_from_row,
    _serialize_normalized_record,
    normalized_records_available,
)
from app.services.hr_import_document_parser import parse_training_fragment, split_numbered_training_fragments

_META_KEY = "_training_review_v1"
_DATE_RE = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b")
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})(?:\s*г\.)?(?=[\s,;.)]|$)", re.IGNORECASE)
_NUMBER_PREFIX_RE = re.compile(r"^\s*\d+[.)]\s*")
_EDITABLE_FIELDS = frozenset({"title", "provider", "hours", "start_date", "end_date"})
_DATE_QUALITY_EXACT = "EXACT"
_DATE_QUALITY_CALCULATED = "CALCULATED"
_DATE_QUALITY_UNKNOWN = "UNKNOWN"
_SPLIT_KEY = "split"
_MANUAL_YEAR_TRANSITION_RE = re.compile(r"(?:19|20)\d{2}\s*г\.\s+(?=[A-ZА-ЯЁ«\"])", re.IGNORECASE)


class TrainingReviewError(Exception):
    pass


class TrainingReviewNotFoundError(TrainingReviewError):
    pass


class TrainingReviewConflictError(TrainingReviewError):
    pass


class TrainingReviewValidationError(TrainingReviewError):
    pass


class TrainingReviewPermissionError(TrainingReviewError):
    pass


def _organization_timezone():
    """Avoid importing the directory router while this service is being imported."""
    from app.control_list_projection.service import organization_timezone

    return organization_timezone()


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _first_monday_of_january(year: int) -> date:
    result = date(year, 1, 1)
    return result + timedelta(days=(7 - result.weekday()) % 7)


def _add_working_days_inclusive(start: date, working_days: int) -> date:
    if working_days <= 1:
        return start
    current = start
    remaining = working_days - 1
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def calculate_year_only_training_dates(year: int, hours: int) -> tuple[date, date]:
    """Use the approved January-Monday/working-day rule for a known year only."""
    start = _first_monday_of_january(year)
    return start, _add_working_days_inclusive(start, max(1, math.ceil(hours / 8)))


def _parse_exact_source_date(source_text: str) -> date | None:
    match = _DATE_RE.search(source_text or "")
    if not match:
        return None
    day_raw, month_raw, year_raw = match.groups()
    year = int(year_raw)
    if year < 100:
        year += 2000
    try:
        return date(year, int(month_raw), int(day_raw))
    except ValueError:
        return None


def _source_year(source_text: str) -> int | None:
    match = _YEAR_RE.search(source_text or "")
    return int(match.group(1)) if match else None


def _strip_meta(override: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in override.items() if key != _META_KEY}


def _meta(override: dict[str, Any]) -> dict[str, Any]:
    value = override.get(_META_KEY)
    return dict(value) if isinstance(value, dict) else {}


def _normalized_hours(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise TrainingReviewValidationError("Количество часов должно быть неотрицательным целым числом.") from exc
    if parsed < 0:
        raise TrainingReviewValidationError("Количество часов должно быть неотрицательным целым числом.")
    return parsed


def _normalized_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TrainingReviewValidationError(f"Поле {field} должно быть строкой.")
    result = value.strip()
    return result or None


def _normalized_date(value: Any, field: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise TrainingReviewValidationError(f"Поле {field} должно иметь формат YYYY-MM-DD.")
    parsed = _date(value)
    if parsed is None:
        raise TrainingReviewValidationError(f"Поле {field} должно иметь формат YYYY-MM-DD.")
    return parsed.isoformat()


def _actor_snapshot(conn: Connection, actor_user_id: int) -> dict[str, Any]:
    row = conn.execute(
        text("SELECT user_id, full_name, login FROM public.users WHERE user_id = :user_id"),
        {"user_id": int(actor_user_id)},
    ).mappings().first()
    if row is None:
        raise TrainingReviewPermissionError("Пользователь-инициатор не найден.")
    return {
        "user_id": int(row["user_id"]),
        "full_name": str(row.get("full_name") or "").strip(),
        "login": str(row.get("login") or "").strip(),
    }


def _payload_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    return {field: payload.get(field) for field in sorted(_EDITABLE_FIELDS)}


def _date_projection(
    *,
    source_text: str,
    payload: dict[str, Any],
    meta: dict[str, Any],
) -> dict[str, Any]:
    stored = meta.get("dates")
    if isinstance(stored, dict):
        return {
            "start_date": stored.get("start_date"),
            "end_date": stored.get("end_date"),
            "start_date_quality": stored.get("start_date_quality", _DATE_QUALITY_UNKNOWN),
            "end_date_quality": stored.get("end_date_quality", _DATE_QUALITY_UNKNOWN),
        }

    start = _date(payload.get("start_date"))
    end = _date(payload.get("end_date"))
    issue = _date(payload.get("issue_date"))
    exact = _parse_exact_source_date(source_text)
    if exact is not None:
        return {
            "start_date": _iso(start),
            "end_date": _iso(end or issue or exact),
            "start_date_quality": _DATE_QUALITY_EXACT if start is not None else _DATE_QUALITY_UNKNOWN,
            "end_date_quality": _DATE_QUALITY_EXACT,
        }

    year = _source_year(source_text)
    hours = _normalized_hours(payload.get("hours"))
    if year is not None and hours is not None:
        calculated_start, calculated_end = calculate_year_only_training_dates(year, hours)
        return {
            "start_date": calculated_start.isoformat(),
            "end_date": calculated_end.isoformat(),
            "start_date_quality": _DATE_QUALITY_CALCULATED,
            "end_date_quality": _DATE_QUALITY_CALCULATED,
        }

    return {
        "start_date": _iso(start),
        "end_date": _iso(end or issue),
        "start_date_quality": _DATE_QUALITY_UNKNOWN,
        "end_date_quality": _DATE_QUALITY_UNKNOWN,
    }


def _append_audit(
    meta: dict[str, Any],
    *,
    row: dict[str, Any],
    version: int,
    action: str,
    actor: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    comment: str | None,
    review_before: dict[str, Any],
    review_after: dict[str, Any],
) -> None:
    history = list(meta.get("history") or [])
    history.append(
        {
            "normalized_record_id": int(row["normalized_record_id"]),
            "batch_id": int(row["batch_id"]),
            "row_id": int(row["row_id"]),
            "version": version,
            "action": action,
            "actor": actor,
            "before": before,
            "after": after,
            "review_before": review_before,
            "review_after": review_after,
            "comment": comment or None,
            "occurred_at": datetime.now(tz=_organization_timezone()[1]).isoformat(),
        }
    )
    meta["history"] = history


def _review_display_status(db_status: str, meta: dict[str, Any]) -> str:
    proposal = meta.get("proposal")
    if isinstance(proposal, dict) and proposal.get("status") == "PENDING":
        return "EMPLOYEE_PROPOSED"
    return {
        REVIEW_STATUS_PENDING: "REQUIRES_REVIEW",
        REVIEW_STATUS_APPROVED: "CHECKED",
        REVIEW_STATUS_REJECTED: "REJECTED",
    }.get(db_status, "REQUIRES_REVIEW")


def _training_record(conn: Connection, row: dict[str, Any]) -> dict[str, Any]:
    serialized = _serialize_normalized_record(row, conn=conn)
    override = _parse_review_override_json(row.get("review_override_json"))
    meta = _meta(override)
    payload = _effective_payload(_parsed_payload_from_row(row), _strip_meta(override))
    dates = _date_projection(source_text=str(row.get("source_text") or ""), payload=payload, meta=meta)
    reviewer = None
    reviewed_by = row.get("reviewed_by")
    if reviewed_by is not None:
        reviewer = _actor_snapshot(conn, int(reviewed_by))
    serialized["title"] = _NUMBER_PREFIX_RE.sub("", str(serialized.get("title") or "")).strip() or None
    serialized["training_review"] = {
        "version": int(meta.get("version") or 1),
        "status": _review_display_status(str(row.get("review_status") or REVIEW_STATUS_PENDING), meta),
        "dates": dates,
        "reviewer": reviewer,
        "reviewed_at": serialized.get("reviewed_at"),
        "proposal": meta.get("proposal") if isinstance(meta.get("proposal"), dict) else None,
        "split": meta.get(_SPLIT_KEY) if isinstance(meta.get(_SPLIT_KEY), dict) else None,
        "history": list(meta.get("history") or []),
    }
    return serialized


def list_training_review_records(conn: Connection, *, employee_id: int) -> dict[str, Any]:
    if not normalized_records_available(conn):
        return {"items": [], "total": 0, "summary": training_review_hours_summary([], as_of=None)}
    rows = conn.execute(
        text(
            """
            SELECT nr.*, r.source_sheet, r.source_row_number,
                   COALESCE(r.normalized_payload->>'education_training_raw', r.normalized_payload->>'training_raw', '') AS source_cell_text,
                   trim(COALESCE(r.normalized_payload->>'full_name', '')) AS full_name,
                   trim(COALESCE(r.normalized_payload->>'iin', '')) AS row_iin,
                   r.normalized_payload->'metadata' AS row_metadata_json,
                   trim(COALESCE(e.full_name, '')) AS directory_employee_name
              FROM public.hr_import_normalized_records nr
              JOIN public.hr_import_rows r ON r.row_id = nr.row_id
              LEFT JOIN public.employees e ON e.employee_id = nr.employee_id
             WHERE nr.employee_id = :employee_id
               AND nr.record_kind = 'training'
               AND nr.review_status IN ('pending', 'approved', 'rejected')
             ORDER BY nr.normalized_record_id
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().all()
    items = [_training_record(conn, dict(row)) for row in rows]
    items.sort(
        key=lambda item: (
            str(item["training_review"]["dates"].get("end_date") or ""),
            int(item["normalized_record_id"]),
        ),
        reverse=True,
    )
    return {"items": items, "total": len(items), "summary": training_review_hours_summary(items, as_of=None)}


def training_batch_summary_projection(conn: Connection, *, batch_id: int) -> dict[str, Any]:
    """Read-only training-review projection for an import-batch dashboard."""
    employees = conn.execute(text("""
        SELECT DISTINCT employee_id FROM public.hr_import_normalized_records
        WHERE batch_id=:batch_id AND record_kind='training' AND employee_id IS NOT NULL
        ORDER BY employee_id
    """), {"batch_id": int(batch_id)}).scalars().all()
    rows: list[dict[str, Any]] = []
    exact = calculated = pending = rejected = manual = source_cells = 0
    for employee_id in employees:
        projection = list_training_review_records(conn, employee_id=int(employee_id))
        items = [item for item in projection["items"] if int(item["batch_id"]) == int(batch_id)]
        if not items:
            continue
        summary = training_review_hours_summary(items, as_of=None)
        statuses = [item["training_review"]["status"] for item in items]
        exact_count = sum(item["training_review"]["dates"].get("end_date_quality") == "EXACT" for item in items)
        calculated_count = sum(item["training_review"]["dates"].get("end_date_quality") == "CALCULATED" for item in items)
        pending_count = sum(status == "REQUIRES_REVIEW" for status in statuses)
        rejected_count = sum(status == "REJECTED" for status in statuses)
        # Raw source is diagnostic only: no record is written or reparsed.
        candidates = [item for item in items if len(split_numbered_training_fragments(str(item.get("source_text") or ""))) == 1 and bool(_MANUAL_YEAR_TRANSITION_RE.search(str(item.get("source_text") or "")))]
        manual_count = len(candidates)
        state = "Нет данных" if not items else "Требуется ручное разделение" if manual_count else "Есть отклонённые записи" if rejected_count else "Проверено" if pending_count == 0 else "Частично проверено" if pending_count < len(items) else "Требуется проверка"
        rows.append({"employee_id": int(employee_id), "course_count": len(items), "exact_dates": exact_count, "calculated_dates": calculated_count, "confirmed_hours_last_5y": summary["confirmed_hours_last_5y"], "preliminary_hours_last_5y": summary["preliminary_hours_last_5y"], "hours_missing": summary["hours_missing"], "pending_count": pending_count, "rejected_count": rejected_count, "manual_split_count": manual_count, "state": state, "training_url": f"/directory/personnel/employees/{int(employee_id)}/card#training", "problem_record_ids": [int(item["normalized_record_id"]) for item in candidates]})
        exact += exact_count; calculated += calculated_count; pending += pending_count; rejected += rejected_count; manual += manual_count
        source_cells += len({int(item["row_id"]) for item in items})
    return {"batch_id": int(batch_id), "employees": rows, "totals": {"employees": len(rows), "source_cells": source_cells, "courses": sum(row["course_count"] for row in rows), "exact_dates": exact, "calculated_dates": calculated, "pending": pending, "rejected": rejected, "manual_split": manual, "below_144": sum(row["preliminary_hours_last_5y"] < 144 for row in rows)}}


def training_split_preview(conn: Connection, *, record_id: int) -> dict[str, Any]:
    """Return only a conservative two-piece proposal; HR must still confirm it."""
    row = _locked_training_row(conn, record_id)
    source = str(row.get("source_text") or "")
    fragments = split_numbered_training_fragments(source)
    if len(fragments) >= 2:
        # Manual review splits one merged row into exactly two children.  The
        # first safe ordinal boundary keeps remaining text for HR review.
        boundary = fragments[1].start_offset
        suggested_by = "ordinal_sequence"
    else:
        # This is only a *manual-review proposal* for an already merged child,
        # never an automatic parser split.  A real completed-year transition is
        # useful to HR, but confirmation remains mandatory in the UI.
        transition = _MANUAL_YEAR_TRANSITION_RE.search(source)
        if transition is None:
            raise TrainingReviewValidationError("Надёжная последовательная граница курсов не найдена; укажите границу вручную.")
        boundary = transition.end()
        suggested_by = "year_transition_for_manual_review"
    return {
        "record_id": int(record_id),
        "version": int(_meta(_parse_review_override_json(row.get("review_override_json"))).get("version") or 1),
        "source_text": source,
        "suggested_boundary": boundary,
        "suggested_by": suggested_by,
        "fragments": [
            {"raw_text": source[:boundary], "start_offset": 0, "end_offset": boundary, "ordinal": fragments[0].ordinal},
            {"raw_text": source[boundary:], "start_offset": boundary, "end_offset": len(source), "ordinal": fragments[1].ordinal if len(fragments) > 1 else None},
        ],
    }


def _split_child_key(parent_id: int, split_group_id: str, order: int) -> str:
    return hashlib.sha256(f"training-manual-split|{parent_id}|{split_group_id}|{order}".encode("utf-8")).hexdigest()


def split_training_review(
    conn: Connection, *, record_id: int, expected_version: int, actor_user_id: int,
    boundary: int | None, children: list[dict[str, Any]] | None, correlation_id: str | None = None,
) -> dict[str, Any]:
    """Atomically supersede a parent and materialize precisely two auditable children."""
    row = _locked_training_row(conn, record_id)
    override = _parse_review_override_json(row.get("review_override_json")); meta = _meta(override)
    if int(meta.get("version") or 1) != expected_version:
        raise TrainingReviewConflictError("Запись была изменена другим пользователем. Обновите страницу и повторите действие.")
    existing = meta.get(_SPLIT_KEY)
    # A child carries inherited provenance under ``split`` too.  Only a record
    # which itself owns child_ids is an already-split parent; otherwise nested
    # manual splitting must remain possible.
    if (
        isinstance(existing, dict)
        and existing.get("state") == "ACTIVE"
        and int(existing.get("parent_record_id") or 0) == int(record_id)
        and existing.get("child_ids")
    ):
        return {"parent_record_id": record_id, "split_group_id": existing["split_group_id"], "idempotent": True}
    source = str(row.get("source_text") or "")
    preview = training_split_preview(conn, record_id=record_id)
    cut = int(boundary if boundary is not None else preview["suggested_boundary"])
    if cut <= 0 or cut >= len(source):
        raise TrainingReviewValidationError("Граница разделения должна находиться внутри исходного текста.")
    pieces = [source[:cut], source[cut:]]
    if not all(piece.strip() for piece in pieces):
        raise TrainingReviewValidationError("Обе дочерние записи должны содержать текст курса.")
    if children is not None and (not isinstance(children, list) or len(children) != 2):
        raise TrainingReviewValidationError("Разделение создаёт ровно две дочерние записи.")
    actor = _actor_snapshot(conn, actor_user_id); group_id = str(uuid.uuid4())
    parent_before = _payload_snapshot(_effective_payload(_parsed_payload_from_row(row), _strip_meta(override)))
    child_ids: list[int] = []
    for index, raw_piece in enumerate(pieces, start=1):
        supplied = (children or [{}, {}])[index - 1]
        if not isinstance(supplied, dict) or set(supplied) - _EDITABLE_FIELDS:
            raise TrainingReviewValidationError("Недопустимые поля дочерней записи.")
        parsed = _parsed_payload_from_row(row)
        # Reparse the individual raw fragment; inheriting the merged parent's
        # first hours/year would double or misdate a child.
        fragment = parse_training_fragment(raw_piece, fragment_index=index)
        payload = dict(parsed)
        payload.update({
            "title": _NUMBER_PREFIX_RE.sub("", str(fragment.title or raw_piece)).strip(),
            "provider": fragment.organization,
            "hours": int(fragment.parsed_hours) if fragment.parsed_hours is not None else None,
            "start_date": fragment.parsed_start_at.isoformat() if fragment.parsed_start_at else None,
            "end_date": (fragment.parsed_end_at or fragment.parsed_issued_at).isoformat() if (fragment.parsed_end_at or fragment.parsed_issued_at) else None,
            "issue_date": fragment.parsed_issued_at.isoformat() if fragment.parsed_issued_at else None,
            "expiry_date": fragment.parsed_valid_until.isoformat() if fragment.parsed_valid_until else None,
            "confidence": fragment.confidence_score,
        })
        if "title" in supplied:
            payload["title"] = _NUMBER_PREFIX_RE.sub("", str(supplied["title"] or raw_piece)).strip()
        for field in _EDITABLE_FIELDS - {"title"}:
            if field in supplied:
                payload[field] = _normalized_hours(supplied[field]) if field == "hours" else (_normalized_date(supplied[field], field) if field in {"start_date", "end_date"} else _normalized_text(supplied[field], field))
        dates = _date_projection(source_text=raw_piece, payload=payload, meta={})
        child_split = {"state": "ACTIVE", "parent_record_id": int(record_id), "parent_version": int(meta.get("version") or 1) + 1, "split_group_id": group_id, "child_order": index, "source_cell_text": source, "fragment_raw": raw_piece, "start_offset": 0 if index == 1 else cut, "end_offset": cut if index == 1 else len(source), "correlation_id": correlation_id or group_id, "actor": actor}
        if isinstance(existing, dict):
            child_split["ancestor_split"] = existing
        child_meta = {
            "version": 1,
            "dates": dates,
            _SPLIT_KEY: child_split,
            "history": [],
        }
        result = conn.execute(text("""
            INSERT INTO public.hr_import_normalized_records
            (batch_id,row_id,employee_id,fragment_index,source_field,source_text,source_record_key,record_kind,document_type_id,document_type_code,title,provider,hours,start_date,end_date,issue_date,expiry_date,document_number,specialty_text,file_url,parse_method,confidence,review_status,review_override_json,review_override_updated_by,review_override_updated_at)
            VALUES (:batch_id,:row_id,:employee_id,:fragment_index,'training_manual_split',:source_text,:source_record_key,'training',:document_type_id,:document_type_code,:title,:provider,:hours,:start_date,:end_date,:issue_date,:expiry_date,:document_number,:specialty_text,:file_url,'manual_override',:confidence,'pending',CAST(:review_override_json AS JSONB),:actor_id,NOW())
            RETURNING normalized_record_id
        """), {**row, **payload, "fragment_index": int(row.get("fragment_index") or 0) * 10 + index, "source_text": raw_piece, "source_record_key": _split_child_key(record_id, group_id, index), "review_override_json": json.dumps({_META_KEY: child_meta}, ensure_ascii=False), "actor_id": actor_user_id}).scalar_one()
        child_ids.append(int(result))
    meta[_SPLIT_KEY] = {"state": "ACTIVE", "split_group_id": group_id, "child_ids": child_ids, "boundary": cut, "actor": actor, "correlation_id": correlation_id or group_id}
    meta["version"] = int(meta.get("version") or 1) + 1
    _append_audit(meta, row=row, version=meta["version"], action="SPLIT", actor=actor, before=parent_before, after={"child_ids": child_ids, "boundary": cut}, comment=None, review_before=_review_snapshot(conn,row), review_after={"status":"superseded"})
    _write_training_review(conn, row=row, expected_version=expected_version, overrides=_strip_meta(override), meta=meta, review_status="superseded", reviewed_by=None, updated_by=actor_user_id)
    return {"parent_record_id": record_id, "split_group_id": group_id, "child_ids": child_ids, "idempotent": False}


def undo_training_review_split(conn: Connection, *, record_id: int, expected_version: int, actor_user_id: int) -> dict[str, Any]:
    row = _locked_training_row(conn, record_id); override = _parse_review_override_json(row.get("review_override_json")); meta = _meta(override)
    split = meta.get(_SPLIT_KEY)
    if not isinstance(split, dict) or split.get("state") != "ACTIVE":
        raise TrainingReviewValidationError("У этой записи нет активного разделения.")
    if int(meta.get("version") or 1) != expected_version:
        raise TrainingReviewConflictError("Запись была изменена другим пользователем. Обновите страницу и повторите действие.")
    child_ids = [int(value) for value in split.get("child_ids") or []]
    used = conn.execute(text("SELECT 1 FROM public.hr_import_normalized_records WHERE normalized_record_id = ANY(:ids) AND (review_status='promoted' OR promoted_document_id IS NOT NULL) LIMIT 1"), {"ids": child_ids}).scalar()
    if used:
        raise TrainingReviewValidationError("Отмена разделения недоступна: дочерняя запись уже используется в последующем каноническом процессе.")
    conn.execute(text("UPDATE public.hr_import_normalized_records SET review_status='superseded', updated_at=NOW() WHERE normalized_record_id = ANY(:ids)"), {"ids": child_ids})
    actor = _actor_snapshot(conn, actor_user_id); split["state"]="UNDONE"; meta[_SPLIT_KEY]=split; meta["version"]=int(meta.get("version") or 1)+1
    _append_audit(meta,row=row,version=meta["version"],action="UNDO_SPLIT",actor=actor,before={"child_ids":child_ids},after={},comment=None,review_before=_review_snapshot(conn,row),review_after={"status":"pending"})
    _write_training_review(conn,row=row,expected_version=expected_version,overrides=_strip_meta(override),meta=meta,review_status=REVIEW_STATUS_PENDING,reviewed_by=None,updated_by=actor_user_id)
    return {"parent_record_id": record_id, "child_ids": child_ids, "idempotent": False}


def training_review_hours_summary(items: Iterable[dict[str, Any]], *, as_of: date | None) -> dict[str, Any]:
    timezone_name, zone = _organization_timezone()
    today = as_of or datetime.now(zone).date()
    official = 0
    preliminary = 0
    expirations: list[tuple[date, int]] = []
    for item in items:
        review = item.get("training_review") or {}
        status = review.get("status")
        hours = _normalized_hours(item.get("hours"))
        end = _date((review.get("dates") or {}).get("end_date"))
        if status not in {"CHECKED", "REQUIRES_REVIEW"} or hours is None or end is None:
            continue
        try:
            expiry = end.replace(year=end.year + 5) + timedelta(days=1)
        except ValueError:  # 29 February
            expiry = end.replace(month=2, day=28, year=end.year + 5) + timedelta(days=1)
        if expiry <= today:
            continue
        if status == "CHECKED":
            official += hours
            expirations.append((expiry, hours))
        preliminary += hours
    expirations.sort()
    nearest = expirations[0] if expirations else None
    remaining_after_nearest = official - nearest[1] if nearest else official
    running = official
    norm_valid_through = None
    if official >= 144:
        for expiry, hours in expirations:
            running -= hours
            if running < 144:
                norm_valid_through = (expiry - timedelta(days=1)).isoformat()
                break
    return {
        "as_of": today.isoformat(),
        "timezone": timezone_name,
        "confirmed_hours_last_5y": official,
        "preliminary_hours_last_5y": preliminary,
        "required_hours": 144,
        "hours_missing": max(0, 144 - official),
        "nearest_exclusion_date": nearest[0].isoformat() if nearest else None,
        "hours_after_nearest_exclusion": remaining_after_nearest if nearest else official,
        "norm_valid_through": norm_valid_through,
    }


def _locked_training_row(conn: Connection, record_id: int) -> dict[str, Any]:
    row = _fetch_normalized_record_row(conn, record_id)
    if row is None or str(row.get("record_kind")) != RECORD_KIND_TRAINING:
        raise TrainingReviewNotFoundError(f"training record {record_id} not found")
    # Lock after the joined read; the mutation below uses an optimistic predicate.
    conn.execute(
        text("SELECT normalized_record_id FROM public.hr_import_normalized_records WHERE normalized_record_id=:record_id FOR UPDATE"),
        {"record_id": int(record_id)},
    )
    refreshed = _fetch_normalized_record_row(conn, record_id)
    if refreshed is None:
        raise TrainingReviewNotFoundError(f"training record {record_id} not found")
    return refreshed


def _write_training_review(
    conn: Connection,
    *,
    row: dict[str, Any],
    expected_version: int,
    overrides: dict[str, Any],
    meta: dict[str, Any],
    review_status: str,
    reviewed_by: int | None,
    updated_by: int,
    preserve_reviewed: bool = False,
) -> dict[str, Any]:
    payload = dict(overrides)
    payload[_META_KEY] = meta
    result = conn.execute(
        text(
            """
            UPDATE public.hr_import_normalized_records
               SET review_override_json = CAST(:review_override_json AS JSONB),
                   review_override_updated_by = :updated_by,
                   review_override_updated_at = NOW(),
                   review_status = :review_status,
                   reviewed_by = CASE WHEN :preserve_reviewed THEN reviewed_by ELSE :reviewed_by END,
                   reviewed_at = CASE
                       WHEN :preserve_reviewed THEN reviewed_at
                       WHEN :reviewed_by IS NULL THEN NULL
                       ELSE NOW()
                   END,
                   updated_at = NOW()
             WHERE normalized_record_id = :record_id
               AND COALESCE((review_override_json -> :meta_key ->> 'version')::BIGINT, 1) = :expected_version
            """
        ),
        {
            "record_id": int(row["normalized_record_id"]),
            "review_override_json": json.dumps(payload, ensure_ascii=False),
            "updated_by": int(updated_by),
            "review_status": review_status,
            "reviewed_by": reviewed_by,
            "meta_key": _META_KEY,
            "expected_version": int(expected_version),
            "preserve_reviewed": bool(preserve_reviewed),
        },
    )
    if result.rowcount != 1:
        raise TrainingReviewConflictError("Запись была изменена другим пользователем. Обновите страницу и повторите действие.")
    updated = _fetch_normalized_record_row(conn, int(row["normalized_record_id"]))
    if updated is None:
        raise TrainingReviewNotFoundError(f"training record {row['normalized_record_id']} not found")
    return _training_record(conn, updated)


def _review_snapshot(conn: Connection, row: dict[str, Any]) -> dict[str, Any]:
    """Preserve a review decision when a later edit returns it to pending."""
    reviewer_id = row.get("reviewed_by")
    return {
        "status": str(row.get("review_status") or REVIEW_STATUS_PENDING),
        "reviewer": _actor_snapshot(conn, int(reviewer_id)) if reviewer_id is not None else None,
        "reviewed_at": _iso(row.get("reviewed_at")),
    }


def update_training_review(
    conn: Connection,
    *,
    record_id: int,
    expected_version: int,
    action: str,
    actor_user_id: int,
    values: dict[str, Any] | None = None,
    comment: str | None = None,
) -> dict[str, Any]:
    """Edit, approve, reject, restore, or decide an employee proposal atomically."""
    if expected_version < 1:
        raise TrainingReviewValidationError("Версия записи должна быть положительной.")
    if action not in {"edit", "approve", "reject", "restore", "accept_proposal", "reject_proposal"}:
        raise TrainingReviewValidationError("Неизвестное действие проверки.")
    row = _locked_training_row(conn, record_id)
    override = _parse_review_override_json(row.get("review_override_json"))
    meta = _meta(override)
    current_version = int(meta.get("version") or 1)
    if current_version != expected_version:
        raise TrainingReviewConflictError("Запись была изменена другим пользователем. Обновите страницу и повторите действие.")
    actor = _actor_snapshot(conn, actor_user_id)
    overrides = _strip_meta(override)
    parsed = _parsed_payload_from_row(row)
    before = _payload_snapshot(_effective_payload(parsed, overrides))
    db_status = str(row.get("review_status") or REVIEW_STATUS_PENDING)
    review_before = _review_snapshot(conn, row)
    proposal = meta.get("proposal") if isinstance(meta.get("proposal"), dict) else None

    if action == "approve" and db_status == REVIEW_STATUS_APPROVED and not (proposal and proposal.get("status") == "PENDING"):
        return _training_record(conn, row)
    if action == "reject" and db_status == REVIEW_STATUS_REJECTED:
        return _training_record(conn, row)

    status = db_status
    reviewed_by: int | None = None
    if action == "edit":
        submitted = values or {}
        unknown = set(submitted) - _EDITABLE_FIELDS
        if unknown:
            raise TrainingReviewValidationError(f"Недопустимые поля: {', '.join(sorted(unknown))}")
        candidate = dict(_effective_payload(parsed, overrides))
        for field, value in submitted.items():
            if field == "hours":
                candidate[field] = _normalized_hours(value)
            elif field in {"start_date", "end_date"}:
                candidate[field] = _normalized_date(value, field)
            else:
                candidate[field] = _normalized_text(value, field)
        start, end = _date(candidate.get("start_date")), _date(candidate.get("end_date"))
        if start and end and start > end:
            raise TrainingReviewValidationError("Дата начала не может быть позже даты окончания.")
        overrides = {field: candidate.get(field) for field in _EDITABLE_FIELDS if candidate.get(field) != parsed.get(field)}
        if "start_date" in submitted or "end_date" in submitted:
            prior_dates = _date_projection(
                source_text=str(row.get("source_text") or ""),
                payload=_effective_payload(parsed, _strip_meta(override)),
                meta=meta,
            )
            meta["dates"] = {
                "start_date": candidate.get("start_date") if "start_date" in submitted else prior_dates["start_date"],
                "end_date": (candidate.get("end_date") or candidate.get("issue_date"))
                if "end_date" in submitted else prior_dates["end_date"],
                "start_date_quality": _DATE_QUALITY_EXACT if "start_date" in submitted and candidate.get("start_date") else prior_dates["start_date_quality"],
                "end_date_quality": _DATE_QUALITY_EXACT if "end_date" in submitted and (candidate.get("end_date") or candidate.get("issue_date")) else prior_dates["end_date_quality"],
            }
        status = REVIEW_STATUS_PENDING
    elif action == "restore":
        overrides = {}
        meta.pop("dates", None)
        status = REVIEW_STATUS_PENDING
    elif action == "approve":
        status = REVIEW_STATUS_APPROVED
        reviewed_by = actor_user_id
    elif action == "reject":
        status = REVIEW_STATUS_REJECTED
        reviewed_by = actor_user_id
    elif action == "accept_proposal":
        if not proposal or proposal.get("status") != "PENDING":
            raise TrainingReviewValidationError("Нет активного предложения сотрудника.")
        proposed_values = proposal.get("values") if isinstance(proposal.get("values"), dict) else {}
        merged = dict(_effective_payload(parsed, overrides))
        merged.update(proposed_values)
        overrides = {field: merged.get(field) for field in _EDITABLE_FIELDS if merged.get(field) != parsed.get(field)}
        if "start_date" in proposed_values or "end_date" in proposed_values:
            prior_dates = _date_projection(
                source_text=str(row.get("source_text") or ""),
                payload=_effective_payload(parsed, _strip_meta(override)),
                meta=meta,
            )
            meta["dates"] = {
                "start_date": proposed_values["start_date"] if "start_date" in proposed_values else prior_dates["start_date"],
                "end_date": proposed_values["end_date"] if "end_date" in proposed_values else prior_dates["end_date"],
                "start_date_quality": (
                    _DATE_QUALITY_EXACT if proposed_values.get("start_date") else _DATE_QUALITY_UNKNOWN
                ) if "start_date" in proposed_values else prior_dates["start_date_quality"],
                "end_date_quality": (
                    _DATE_QUALITY_EXACT if proposed_values.get("end_date") else _DATE_QUALITY_UNKNOWN
                ) if "end_date" in proposed_values else prior_dates["end_date_quality"],
            }
        proposal["status"] = "ACCEPTED"
        proposal["decided_by"] = actor
        proposal["decided_at"] = datetime.now(tz=_organization_timezone()[1]).isoformat()
        meta["proposal"] = proposal
        status = REVIEW_STATUS_APPROVED
        reviewed_by = actor_user_id
    else:  # reject_proposal
        if not proposal or proposal.get("status") != "PENDING":
            raise TrainingReviewValidationError("Нет активного предложения сотрудника.")
        proposal["status"] = "REJECTED"
        proposal["decided_by"] = actor
        proposal["decided_at"] = datetime.now(tz=_organization_timezone()[1]).isoformat()
        meta["proposal"] = proposal

    after = _payload_snapshot(_effective_payload(parsed, overrides))
    meta["version"] = current_version + 1
    _append_audit(
        meta,
        row=row,
        version=meta["version"],
        action=action.upper(),
        actor=actor,
        before=before,
        after=after,
        comment=comment,
        review_before=review_before,
        review_after={"status": status, "reviewer": actor if reviewed_by is not None else None},
    )
    return _write_training_review(
        conn,
        row=row,
        expected_version=expected_version,
        overrides=overrides,
        meta=meta,
        review_status=status,
        reviewed_by=reviewed_by,
        updated_by=actor_user_id,
        preserve_reviewed=action == "reject_proposal",
    )


def submit_employee_training_proposal(
    conn: Connection,
    *,
    record_id: int,
    expected_version: int,
    actor_user_id: int,
    values: dict[str, Any],
    comment: str | None = None,
) -> dict[str, Any]:
    row = _locked_training_row(conn, record_id)
    owner_employee_id = row.get("employee_id")
    actor = _actor_snapshot(conn, actor_user_id)
    actor_employee_id = conn.execute(
        text("SELECT employee_id FROM public.users WHERE user_id=:user_id"), {"user_id": int(actor_user_id)}
    ).scalar()
    if owner_employee_id is None or actor_employee_id is None or int(owner_employee_id) != int(actor_employee_id):
        raise TrainingReviewPermissionError("Можно предложить исправление только для собственной записи обучения.")
    override = _parse_review_override_json(row.get("review_override_json"))
    meta = _meta(override)
    current_version = int(meta.get("version") or 1)
    if current_version != expected_version:
        raise TrainingReviewConflictError("Запись была изменена другим пользователем. Обновите страницу и повторите действие.")
    unknown = set(values) - _EDITABLE_FIELDS
    if unknown:
        raise TrainingReviewValidationError(f"Недопустимые поля: {', '.join(sorted(unknown))}")
    proposal_values: dict[str, Any] = {}
    for field, value in values.items():
        proposal_values[field] = (
            _normalized_hours(value) if field == "hours" else _normalized_date(value, field)
            if field in {"start_date", "end_date"} else _normalized_text(value, field)
        )
    overrides = _strip_meta(override)
    parsed = _parsed_payload_from_row(row)
    before = _payload_snapshot(_effective_payload(parsed, overrides))
    review_before = _review_snapshot(conn, row)
    existing = meta.get("proposal") if isinstance(meta.get("proposal"), dict) else None
    if existing and existing.get("status") == "PENDING" and existing.get("values") == proposal_values:
        return _training_record(conn, row)
    meta["proposal"] = {
        "status": "PENDING",
        "values": proposal_values,
        "submitted_by": actor,
        "submitted_at": datetime.now(tz=_organization_timezone()[1]).isoformat(),
    }
    meta["version"] = current_version + 1
    _append_audit(
        meta,
        row=row,
        version=meta["version"],
        action="EMPLOYEE_PROPOSED",
        actor=actor,
        before=before,
        after=proposal_values,
        comment=comment,
        review_before=review_before,
        review_after=review_before,
    )
    return _write_training_review(
        conn,
        row=row,
        expected_version=expected_version,
        overrides=overrides,
        meta=meta,
        review_status=str(row.get("review_status") or REVIEW_STATUS_PENDING),
        reviewed_by=None,
        updated_by=actor_user_id,
        preserve_reviewed=True,
    )


def initialize_training_review_dates(conn: Connection, *, batch_id: int) -> int:
    """Persist derived date/provenance metadata for a locally imported batch once.

    It is idempotent and does not overwrite a manually edited review payload.
    """
    rows = conn.execute(
        text(
            """
            SELECT normalized_record_id, source_text, hours, start_date, end_date, issue_date, review_override_json
            FROM public.hr_import_normalized_records
            WHERE batch_id=:batch_id AND record_kind='training'
            FOR UPDATE
            """
        ),
        {"batch_id": int(batch_id)},
    ).mappings().all()
    updated = 0
    for row in rows:
        override = _parse_review_override_json(row.get("review_override_json"))
        meta = _meta(override)
        if isinstance(meta.get("dates"), dict):
            continue
        payload = {
            "hours": row.get("hours"),
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
            "issue_date": row.get("issue_date"),
        }
        meta["version"] = int(meta.get("version") or 1)
        meta["dates"] = _date_projection(source_text=str(row.get("source_text") or ""), payload=payload, meta={})
        override[_META_KEY] = meta
        conn.execute(
            text("UPDATE public.hr_import_normalized_records SET review_override_json=CAST(:payload AS JSONB), updated_at=NOW() WHERE normalized_record_id=:record_id"),
            {"record_id": int(row["normalized_record_id"]), "payload": json.dumps(override, ensure_ascii=False)},
        )
        updated += 1
    return updated
