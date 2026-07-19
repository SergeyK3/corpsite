"""HR-facing read model: department → employees → detected differences."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.engine import Connection

from app.mrd.domain.difference_models import DetectedDifferenceRecord
from app.mrd.domain.errors import MrdNotFoundError
from app.mrd.domain.field_labels import get_field_label
from app.mrd.domain.types import (
    DIFFERENCE_LIFECYCLE_CONFIRMED,
    DIFFERENCE_LIFECYCLE_DETECTED,
    DIFFERENCE_LIFECYCLE_REJECTED,
    DIFFERENCE_LIFECYCLE_SUPERSEDED,
)
from app.mrd.infrastructure.repository import MrdEntryRow, MrdVersionDetailRow, SqlAlchemyMrdRepository
from app.services.department_recoding_service import list_recoding_options

_EMP_MATCH = re.compile(r"^emp:(\d+)$")

REVIEW_STATUS_NO_CHANGES = "NO_CHANGES"
REVIEW_STATUS_PENDING = "PENDING"
REVIEW_STATUS_PARTIAL = "PARTIAL"
REVIEW_STATUS_REVIEWED = "REVIEWED"


def roster_match_key(entity_scope: str) -> str:
    return entity_scope.split("|", 1)[0]


def parse_employee_id(match_key: str) -> int | None:
    matched = _EMP_MATCH.match(match_key.strip())
    if not matched:
        return None
    return int(matched.group(1))


def _payload_text(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _employee_display(entry: MrdEntryRow) -> dict[str, Any]:
    payload = entry.effective_payload or {}
    return {
        "match_key": entry.match_key,
        "employee_id": parse_employee_id(entry.match_key),
        "full_name": _payload_text(payload, "full_name") or entry.match_key,
        "position_raw": _payload_text(payload, "position_raw") or "—",
        "rate": _payload_text(payload, "rate", "part_time", "workload", "employment_type"),
        "category": _payload_text(payload, "certification_raw", "category"),
    }


def _difference_source_label(origin_context: dict[str, Any]) -> str | None:
    batch_id = origin_context.get("batch_id")
    if batch_id is not None:
        return f"Импорт #{batch_id}"
    return None


def _decision_status(lifecycle_status: str) -> str:
    if lifecycle_status == DIFFERENCE_LIFECYCLE_DETECTED:
        return "AWAITING"
    if lifecycle_status == DIFFERENCE_LIFECYCLE_CONFIRMED:
        return "CONFIRMED"
    if lifecycle_status == DIFFERENCE_LIFECYCLE_REJECTED:
        return "REJECTED"
    return lifecycle_status


def _employee_review_status(differences: list[DetectedDifferenceRecord]) -> str:
    active = [row for row in differences if row.lifecycle_status != DIFFERENCE_LIFECYCLE_SUPERSEDED]
    if not active:
        return REVIEW_STATUS_NO_CHANGES
    statuses = {row.lifecycle_status for row in active}
    if statuses == {DIFFERENCE_LIFECYCLE_DETECTED}:
        return REVIEW_STATUS_PENDING
    if DIFFERENCE_LIFECYCLE_DETECTED in statuses:
        return REVIEW_STATUS_PARTIAL
    return REVIEW_STATUS_REVIEWED


def _difference_to_dict(row: DetectedDifferenceRecord) -> dict[str, Any]:
    origin = row.origin_context or {}
    return {
        "difference_id": row.difference_id,
        "attribute": row.attribute,
        "field_label": get_field_label(row.attribute, record_kind=row.record_kind),
        "old_value": row.old_value,
        "new_value": row.new_value,
        "detected_value": row.new_value,
        "source_label": _difference_source_label(origin),
        "lifecycle_status": row.lifecycle_status,
        "decision_status": _decision_status(row.lifecycle_status),
        "technical_diff_class": row.technical_diff_class,
        "record_kind": row.record_kind,
        "row_version": row.row_version,
        "actions_available": False,
    }


def _index_differences_by_roster(
    differences: list[DetectedDifferenceRecord],
) -> dict[str, list[DetectedDifferenceRecord]]:
    grouped: dict[str, list[DetectedDifferenceRecord]] = {}
    for row in differences:
        key = roster_match_key(row.entity_scope)
        grouped.setdefault(key, []).append(row)
    return grouped


def _filter_departments(
    departments: list[dict[str, Any]],
    *,
    org_group_id: int | None,
    effective_log_group: str | None,
    group_slug_to_id: dict[str, int],
) -> list[dict[str, Any]]:
    if org_group_id is not None:
        return [row for row in departments if int(row.get("org_group_id") or 0) == org_group_id]
    if effective_log_group:
        mapped_id = group_slug_to_id.get(effective_log_group)
        if mapped_id is not None:
            return [row for row in departments if int(row.get("org_group_id") or 0) == mapped_id]
    return departments


@dataclass(frozen=True, slots=True)
class HrReviewSnapshot:
    summary: MrdVersionDetailRow
    org_groups: tuple[dict[str, Any], ...]
    departments: tuple[dict[str, Any], ...]
    department_summary: dict[str, int] | None
    employees: tuple[dict[str, Any], ...]
    employees_total: int


def fetch_hr_review(
    conn: Connection,
    *,
    mrd_id: int,
    org_group_id: int | None = None,
    effective_log_group: str | None = None,
    org_unit_id: int | None = None,
    changed_only: bool = True,
    search: str | None = None,
    review_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> HrReviewSnapshot:
    repo = SqlAlchemyMrdRepository(conn)
    summary = repo.load_mrd_version_detail(mrd_id)
    if summary is None:
        raise MrdNotFoundError(f"mrd_id={mrd_id} not found")

    recoding = list_recoding_options(conn)
    org_groups = tuple(recoding.get("groups") or [])
    departments_raw = list(recoding.get("departments") or [])
    slug_to_id = {
        str(group.get("value") or ""): int(group["group_id"])
        for group in org_groups
        if group.get("group_id") is not None
    }
    departments = _filter_departments(
        departments_raw,
        org_group_id=org_group_id,
        effective_log_group=effective_log_group,
        group_slug_to_id=slug_to_id,
    )

    if org_unit_id is None:
        return HrReviewSnapshot(
            summary=summary,
            org_groups=org_groups,
            departments=tuple(departments),
            department_summary=None,
            employees=(),
            employees_total=0,
        )

    all_entries = repo.list_all_roster_entries_for_org_unit(
        mrd_id=mrd_id,
        org_unit_id=org_unit_id,
        search=search,
    )
    all_diffs = repo.list_differences_for_mrd(mrd_id)
    diffs_by_roster = _index_differences_by_roster(all_diffs)

    department_summary = {
        "total_employees": 0,
        "without_changes": 0,
        "with_changes": 0,
        "awaiting_decision": 0,
        "confirmed": 0,
        "rejected": 0,
    }

    employee_rows: list[dict[str, Any]] = []
    for entry in all_entries:
        roster_key = entry.match_key
        employee_diffs = diffs_by_roster.get(roster_key, [])
        active_diffs = [row for row in employee_diffs if row.lifecycle_status != DIFFERENCE_LIFECYCLE_SUPERSEDED]
        status = _employee_review_status(employee_diffs)

        department_summary["total_employees"] += 1
        if status == REVIEW_STATUS_NO_CHANGES:
            department_summary["without_changes"] += 1
        else:
            department_summary["with_changes"] += 1
        if status in {REVIEW_STATUS_PENDING, REVIEW_STATUS_PARTIAL}:
            department_summary["awaiting_decision"] += 1
        department_summary["confirmed"] += sum(
            1 for row in active_diffs if row.lifecycle_status == DIFFERENCE_LIFECYCLE_CONFIRMED
        )
        department_summary["rejected"] += sum(
            1 for row in active_diffs if row.lifecycle_status == DIFFERENCE_LIFECYCLE_REJECTED
        )

        if changed_only and status == REVIEW_STATUS_NO_CHANGES:
            continue
        if review_status and status != review_status:
            continue

        display = _employee_display(entry)
        employee_rows.append(
            {
                **display,
                "difference_count": len(active_diffs),
                "review_status": status,
                "differences": [_difference_to_dict(row) for row in active_diffs],
            }
        )

    employees_total = len(employee_rows)
    page = employee_rows[offset : offset + limit]

    return HrReviewSnapshot(
        summary=summary,
        org_groups=org_groups,
        departments=tuple(departments),
        department_summary=department_summary,
        employees=tuple(page),
        employees_total=employees_total,
    )


def hr_review_to_dict(snapshot: HrReviewSnapshot) -> dict[str, Any]:
    summary = snapshot.summary
    return {
        "summary": {
            "mrd_id": summary.mrd_id,
            "report_period": summary.report_period,
            "version": summary.version,
            "status": summary.status,
            "row_version": summary.row_version,
            "entry_count": summary.entry_count,
            "forked_from_reference_id": summary.forked_from_reference_id,
            "is_active_for_period": summary.status == "ACTIVE",
        },
        "org_groups": list(snapshot.org_groups),
        "departments": list(snapshot.departments),
        "department_summary": snapshot.department_summary,
        "employees": {
            "total": snapshot.employees_total,
            "items": list(snapshot.employees),
        },
    }
