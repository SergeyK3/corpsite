"""Read-only HR import staging analytics (ADR-038 Analytics MVP)."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.hr_import import (
    CLASSIFICATION_CATEGORY_ROW,
    CLASSIFICATION_DECLARATION,
    CLASSIFICATION_DUPLICATE_IIN,
    CLASSIFICATION_INVALID_IIN,
    CLASSIFICATION_SUMMARY_ROW,
    ROW_TYPE_EMPLOYEE,
)
from scripts.import_hr_control_list import mask_iin

TECHNICAL_CLASSIFICATIONS = frozenset(
    {
        CLASSIFICATION_DECLARATION,
        CLASSIFICATION_SUMMARY_ROW,
        CLASSIFICATION_CATEGORY_ROW,
    }
)

AGE_BUCKETS: tuple[tuple[str, int, Optional[int]], ...] = (
    ("under_30", 0, 29),
    ("30_39", 30, 39),
    ("40_49", 40, 49),
    ("50_59", 50, 59),
    ("60_64", 60, 64),
    ("65_plus", 65, None),
)

AGE_BUCKET_LABELS: dict[str, str] = {
    "under_30": "до 30",
    "30_39": "30–39",
    "40_49": "40–49",
    "50_59": "50–59",
    "60_64": "60–64",
    "65_plus": "65+",
}

STAFF_TYPE_LABELS: dict[str, str] = {
    "doctors": "врачи",
    "nurses": "медсестра / СМР",
    "junior_staff": "санитарки / младший персонал",
    "other_staff": "прочие",
    "part_time": "совместители",
    "declaration": "декларации",
}


class BatchNotFoundError(LookupError):
    pass


def _parse_birth_date(value: str) -> Optional[date]:
    text_val = (value or "").strip()
    if not text_val:
        return None
    try:
        return date.fromisoformat(text_val[:10])
    except ValueError:
        return None


def _calc_age(birth: date, *, on: Optional[date] = None) -> int:
    today = on or date.today()
    years = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        years -= 1
    return years


def _age_bucket(age: Optional[int]) -> Optional[str]:
    if age is None:
        return None
    for key, low, high in AGE_BUCKETS:
        if high is None:
            if age >= low:
                return key
        elif low <= age <= high:
            return key
    return None


def _normalize_position(value: str) -> str:
    text_val = (value or "").strip().lower()
    text_val = re.sub(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}", " ", text_val)
    text_val = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text_val)
    text_val = re.sub(r"\s+", " ", text_val).strip(" ,;.")
    return text_val or "—"


def _classify_certification(value: str) -> str:
    text_val = (value or "").strip().lower()
    if not text_val:
        return "none"
    if "высш" in text_val:
        return "highest"
    if "перва" in text_val or re.search(r"\b1\b", text_val):
        return "first"
    if "втор" in text_val or re.search(r"\b2\b", text_val):
        return "second"
    if "сертификат" in text_val:
        return "certificate"
    return "other"


def is_real_employee_row(row: dict[str, Any]) -> bool:
    """True for actual staff rows on employee roster sheets."""
    if row.get("is_employee_roster") is False:
        return False
    row_type = str(row.get("row_type") or "")
    if row_type:
        return row_type == ROW_TYPE_EMPLOYEE
    if row.get("classification") in TECHNICAL_CLASSIFICATIONS:
        return False
    if row.get("sheet_type") == "declaration":
        return False
    return True


def is_declaration_row(row: dict[str, Any]) -> bool:
    return row.get("sheet_type") == "declaration" or row.get("classification") == CLASSIFICATION_DECLARATION


def is_technical_no_iin_row(row: dict[str, Any]) -> bool:
    if is_declaration_row(row):
        return False
    return not row.get("iin") and not is_real_employee_row(row)


def is_declaration_no_iin_row(row: dict[str, Any]) -> bool:
    return is_declaration_row(row) and not row.get("iin")


def is_missing_iin_employee_row(row: dict[str, Any]) -> bool:
    return is_real_employee_row(row) and not row.get("iin")


def _ensure_batch_exists(conn: Connection, batch_id: int) -> None:
    row = conn.execute(
        text("SELECT 1 FROM public.hr_import_batches WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    ).first()
    if not row:
        raise BatchNotFoundError(f"batch_id={batch_id} not found")


def _load_staging_rows(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    _ensure_batch_exists(conn, batch_id)
    db_rows = conn.execute(
        text(
            """
            SELECT
                row_id,
                source_sheet,
                source_row_number,
                normalized_payload,
                error_codes
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
            ORDER BY row_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()

    items: list[dict[str, Any]] = []
    for db_row in db_rows:
        payload = dict(db_row["normalized_payload"] or {})
        metadata = dict(payload.pop("metadata", {}) or {})
        sheet_type = str(metadata.get("sheet_type", "") or "")
        classification = str(metadata.get("classification", "") or "")
        row_type = str(metadata.get("row_type", "") or "")
        declaration_group = str(metadata.get("declaration_group", "") or "")
        is_employee_roster = bool(metadata.get("is_employee_roster", row_type == ROW_TYPE_EMPLOYEE))
        iin_valid = bool(metadata.get("iin_valid", False))
        iin = str(payload.get("iin", "") or "").strip()
        birth = _parse_birth_date(str(payload.get("birth_date", "") or ""))
        age = _calc_age(birth) if birth else None

        items.append(
            {
                "row_id": int(db_row["row_id"]),
                "source_sheet": str(db_row["source_sheet"] or ""),
                "source_row_number": int(db_row["source_row_number"]),
                "full_name": str(payload.get("full_name", "") or "").strip(),
                "iin": iin,
                "iin_masked": mask_iin(iin),
                "iin_valid": iin_valid,
                "birth_date": birth.isoformat() if birth else "",
                "age": age,
                "age_bucket": _age_bucket(age),
                "department": str(payload.get("department", "") or "").strip(),
                "position_raw": str(payload.get("position_raw", "") or "").strip(),
                "position_normalized": _normalize_position(str(payload.get("position_raw", "") or "")),
                "training_raw": str(payload.get("training_raw", "") or "").strip(),
                "certification_raw": str(payload.get("certification_raw", "") or "").strip(),
                "certification_group": _classify_certification(str(payload.get("certification_raw", "") or "")),
                "sheet_type": sheet_type,
                "classification": classification,
                "row_type": row_type,
                "declaration_group": declaration_group,
                "is_employee_roster": is_employee_roster,
                "error_codes": list(db_row["error_codes"] or []),
                "has_training": bool(str(payload.get("training_raw", "") or "").strip()),
                "has_certification": bool(str(payload.get("certification_raw", "") or "").strip()),
            }
        )
    return items


def list_batches(conn: Connection) -> dict[str, Any]:
    rows = conn.execute(
        text(
            """
            SELECT
                batch_id, file_name, imported_at, status,
                total_rows, valid_rows, error_rows
            FROM public.hr_import_batches
            ORDER BY imported_at DESC, batch_id DESC
            """
        )
    ).mappings().all()
    return {
        "items": [
            {
                "batch_id": int(r["batch_id"]),
                "file_name": r["file_name"],
                "imported_at": r["imported_at"].isoformat() if r["imported_at"] else None,
                "status": r["status"],
                "total_rows": int(r["total_rows"]),
                "valid_rows": int(r["valid_rows"]),
                "error_rows": int(r["error_rows"]),
            }
            for r in rows
        ]
    }


def batch_summary(conn: Connection, batch_id: int) -> dict[str, Any]:
    rows = _load_staging_rows(conn, batch_id)
    employee_rows = [r for r in rows if is_real_employee_row(r)]
    iin_counts = Counter(r["iin"] for r in employee_rows if r["iin"])
    duplicate_iins = {iin for iin, count in iin_counts.items() if count > 1}

    by_sheet_type: dict[str, int] = defaultdict(int)
    for row in employee_rows:
        key = row["sheet_type"] or "other_staff"
        by_sheet_type[key] += 1

    by_declaration_group: dict[str, int] = defaultdict(int)
    for row in rows:
        if is_declaration_row(row) and row.get("declaration_group"):
            by_declaration_group[row["declaration_group"]] += 1

    return {
        "batch_id": batch_id,
        "total_rows": len(rows),
        "employee_roster_rows": len(employee_rows),
        "declaration_rows": sum(1 for r in rows if is_declaration_row(r)),
        "technical_category_rows": sum(
            1 for r in rows if not is_real_employee_row(r) and not is_declaration_row(r)
        ),
        "valid_iin": sum(1 for r in employee_rows if r["iin_valid"]),
        "by_sheet_type": {k: by_sheet_type.get(k, 0) for k in STAFF_TYPE_LABELS if k != "declaration"},
        "by_declaration_group": dict(by_declaration_group),
        "with_training": sum(1 for r in employee_rows if r["has_training"]),
        "with_certification": sum(1 for r in employee_rows if r["has_certification"]),
        "missing_full_name": sum(1 for r in employee_rows if not r["full_name"]),
        "missing_iin": sum(1 for r in rows if is_missing_iin_employee_row(r)),
        "technical_no_iin_rows": sum(1 for r in rows if is_technical_no_iin_row(r)),
        "declaration_no_iin_rows": sum(1 for r in rows if is_declaration_no_iin_row(r)),
        "invalid_iin": sum(1 for r in employee_rows if r["iin"] and not r["iin_valid"]),
        "duplicate_iin_groups": len(duplicate_iins),
        "duplicate_iin_rows": sum(1 for r in employee_rows if r["iin"] in duplicate_iins),
    }


def age_distribution(conn: Connection, batch_id: int) -> dict[str, Any]:
    rows = [r for r in _load_staging_rows(conn, batch_id) if is_real_employee_row(r)]
    counts = {key: 0 for key, _, _ in AGE_BUCKETS}
    counts["unknown"] = 0
    for row in rows:
        bucket = row["age_bucket"]
        if bucket:
            counts[bucket] += 1
        else:
            counts["unknown"] += 1
    return {
        "batch_id": batch_id,
        "buckets": [
            {"key": key, "label": AGE_BUCKET_LABELS[key], "count": counts[key]}
            for key, _, _ in AGE_BUCKETS
        ],
        "unknown": counts["unknown"],
    }


def department_analytics(conn: Connection, batch_id: int) -> dict[str, Any]:
    rows = [r for r in _load_staging_rows(conn, batch_id) if is_real_employee_row(r)]
    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        dept = row["department"] or "— не указано —"
        bucket = grouped.setdefault(
            dept,
            {
                "department": dept,
                "total": 0,
                "doctors": 0,
                "nurses": 0,
                "junior_staff": 0,
                "other": 0,
                "with_training": 0,
                "with_certification": 0,
                "age_65_plus": 0,
                "ages": [],
            },
        )
        bucket["total"] += 1
        st = row["sheet_type"]
        if st == "doctors":
            bucket["doctors"] += 1
        elif st == "nurses":
            bucket["nurses"] += 1
        elif st == "junior_staff":
            bucket["junior_staff"] += 1
        else:
            bucket["other"] += 1
        if row["has_training"]:
            bucket["with_training"] += 1
        if row["has_certification"]:
            bucket["with_certification"] += 1
        if row["age"] is not None and row["age"] >= 65:
            bucket["age_65_plus"] += 1
        if row["age"] is not None:
            bucket["ages"].append(row["age"])

    items = []
    for dept, bucket in grouped.items():
        ages = bucket.pop("ages")
        avg = round(sum(ages) / len(ages), 1) if ages else None
        bucket["average_age"] = avg
        items.append(bucket)

    items.sort(key=lambda x: (-x["total"], x["department"]))
    return {"batch_id": batch_id, "items": items}


def position_analytics(conn: Connection, batch_id: int, *, limit: int = 20) -> dict[str, Any]:
    rows = [r for r in _load_staging_rows(conn, batch_id) if is_real_employee_row(r)]
    counts = Counter(r["position_normalized"] for r in rows if r["position_normalized"] != "—")
    top = counts.most_common(limit)
    return {
        "batch_id": batch_id,
        "items": [{"position": name, "count": count} for name, count in top],
    }


def training_analytics(conn: Connection, batch_id: int) -> dict[str, Any]:
    rows = _load_staging_rows(conn, batch_id)
    employee_rows = [r for r in rows if is_real_employee_row(r)]
    with_training = [r for r in employee_rows if r["has_training"]]
    by_department = Counter(r["department"] or "— не указано —" for r in with_training)
    by_staff_type = Counter(r["sheet_type"] or "other_staff" for r in with_training)

    dept_totals = Counter(r["department"] or "— не указано —" for r in employee_rows)
    without_by_dept = {
        dept: total - by_department.get(dept, 0)
        for dept, total in dept_totals.items()
    }
    top_without = sorted(without_by_dept.items(), key=lambda x: (-x[1], x[0]))[:10]

    examples = []
    for row in with_training[:5]:
        sample = row["training_raw"]
        if len(sample) > 120:
            sample = sample[:120] + "…"
        examples.append(
            {
                "row_id": row["row_id"],
                "full_name": row["full_name"],
                "department": row["department"],
                "training_raw": sample,
            }
        )

    return {
        "batch_id": batch_id,
        "total_with_training": len(with_training),
        "by_department": [
            {"department": dept, "count": count}
            for dept, count in by_department.most_common()
        ],
        "by_staff_type": [
            {"sheet_type": st, "label": STAFF_TYPE_LABELS.get(st, st), "count": count}
            for st, count in by_staff_type.most_common()
        ],
        "top_departments_without_training": [
            {"department": dept, "count_without": count}
            for dept, count in top_without
        ],
        "examples": examples,
    }


def certification_analytics(conn: Connection, batch_id: int) -> dict[str, Any]:
    rows = _load_staging_rows(conn, batch_id)
    employee_rows = [r for r in rows if is_real_employee_row(r)]
    with_cert = [r for r in employee_rows if r["has_certification"]]
    group_labels = {
        "highest": "высшая категория",
        "first": "первая категория",
        "second": "вторая категория",
        "certificate": "сертификат",
        "other": "прочее",
        "none": "без категории/сертификата",
    }
    by_group = Counter(r["certification_group"] for r in employee_rows)
    by_department = Counter(r["department"] or "— не указано —" for r in with_cert)

    examples = []
    for row in with_cert[:5]:
        sample = row["certification_raw"]
        if len(sample) > 120:
            sample = sample[:120] + "…"
        examples.append(
            {
                "row_id": row["row_id"],
                "full_name": row["full_name"],
                "department": row["department"],
                "certification_raw": sample,
                "group": row["certification_group"],
            }
        )

    return {
        "batch_id": batch_id,
        "total_with_certification": len(with_cert),
        "by_group": [
            {
                "group": key,
                "label": group_labels.get(key, key),
                "count": by_group.get(key, 0),
            }
            for key in ("highest", "first", "second", "certificate", "other", "none")
        ],
        "by_department": [
            {"department": dept, "count": count}
            for dept, count in by_department.most_common()
        ],
        "examples": examples,
    }


def risk_analytics(conn: Connection, batch_id: int) -> dict[str, Any]:
    rows = _load_staging_rows(conn, batch_id)
    employee_rows = [r for r in rows if is_real_employee_row(r)]
    iin_counts = Counter(r["iin"] for r in employee_rows if r["iin"])
    duplicate_iins = {iin for iin, count in iin_counts.items() if count > 1}

    def _risk(key: str, label: str, predicate) -> dict[str, Any]:
        matched = [r for r in rows if predicate(r)]
        return {
            "risk_type": key,
            "label": label,
            "count": len(matched),
            "row_ids": [r["row_id"] for r in matched[:50]],
        }

    risks = [
        _risk(
            "age_65_plus",
            "Сотрудники 65+",
            lambda r: is_real_employee_row(r) and r["age"] is not None and r["age"] >= 65,
        ),
        _risk("missing_iin", "Без ИИН", is_missing_iin_employee_row),
        _risk("technical_no_iin", "Служебные/категорийные без ИИН", is_technical_no_iin_row),
        _risk("declaration_no_iin", "Декларации без ИИН", is_declaration_no_iin_row),
        _risk(
            "invalid_iin",
            "Некорректный ИИН",
            lambda r: is_real_employee_row(r) and r["classification"] == CLASSIFICATION_INVALID_IIN,
        ),
        _risk(
            "duplicate_iin",
            "Дубликаты ИИН",
            lambda r: is_real_employee_row(r)
            and (r["iin"] in duplicate_iins or r["classification"] == CLASSIFICATION_DUPLICATE_IIN),
        ),
        _risk(
            "without_training",
            "Без обучения",
            lambda r: is_real_employee_row(r) and not r["has_training"],
        ),
        _risk(
            "without_certification",
            "Без категории/сертификата",
            lambda r: is_real_employee_row(r) and not r["has_certification"],
        ),
        _risk(
            "unknown_department",
            "Неизвестное отделение",
            lambda r: is_real_employee_row(r) and not r["department"],
        ),
        _risk(
            "summary_rows",
            "Итоговые/служебные строки",
            lambda r: r["classification"] in (CLASSIFICATION_SUMMARY_ROW, CLASSIFICATION_CATEGORY_ROW),
        ),
        _risk(
            "declaration_rows",
            "Декларационные строки",
            lambda r: is_declaration_row(r),
        ),
    ]
    return {"batch_id": batch_id, "items": risks}


def _row_matches_risk(row: dict[str, Any], risk_type: str, duplicate_iins: set[str]) -> bool:
    if risk_type == "age_65_plus":
        return is_real_employee_row(row) and row["age"] is not None and row["age"] >= 65
    if risk_type == "missing_iin":
        return is_missing_iin_employee_row(row)
    if risk_type == "technical_no_iin":
        return is_technical_no_iin_row(row)
    if risk_type == "declaration_no_iin":
        return is_declaration_no_iin_row(row)
    if risk_type == "invalid_iin":
        return is_real_employee_row(row) and row["classification"] == CLASSIFICATION_INVALID_IIN
    if risk_type == "duplicate_iin":
        return is_real_employee_row(row) and (
            row["iin"] in duplicate_iins or row["classification"] == CLASSIFICATION_DUPLICATE_IIN
        )
    if risk_type == "without_training":
        return is_real_employee_row(row) and not row["has_training"]
    if risk_type == "without_certification":
        return is_real_employee_row(row) and not row["has_certification"]
    if risk_type == "unknown_department":
        return is_real_employee_row(row) and not row["department"]
    if risk_type == "summary_rows":
        return row["classification"] in (CLASSIFICATION_SUMMARY_ROW, CLASSIFICATION_CATEGORY_ROW)
    if risk_type == "declaration_rows":
        return is_declaration_row(row)
    return False


def _matches_roster_scope(row: dict[str, Any], roster_scope: Optional[str]) -> bool:
    if not roster_scope or roster_scope == "all":
        return True
    if roster_scope == "personnel":
        return is_real_employee_row(row)
    if roster_scope == "declaration":
        return is_declaration_row(row)
    if roster_scope == "technical":
        return not is_real_employee_row(row) and not is_declaration_row(row)
    return True


def list_batch_rows(
    conn: Connection,
    batch_id: int,
    *,
    department: Optional[str] = None,
    sheet_type: Optional[str] = None,
    age_bucket: Optional[str] = None,
    has_training: Optional[bool] = None,
    has_certification: Optional[bool] = None,
    risk_type: Optional[str] = None,
    roster_scope: Optional[str] = None,
    q_name: Optional[str] = None,
    q_position: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    rows = _load_staging_rows(conn, batch_id)
    employee_rows = [r for r in rows if is_real_employee_row(r)]
    iin_counts = Counter(r["iin"] for r in employee_rows if r["iin"])
    duplicate_iins = {iin for iin, count in iin_counts.items() if count > 1}

    filtered = rows
    if roster_scope:
        filtered = [r for r in filtered if _matches_roster_scope(r, roster_scope)]
    if department:
        filtered = [r for r in filtered if r["department"] == department]
    if sheet_type:
        filtered = [r for r in filtered if r["sheet_type"] == sheet_type]
    if age_bucket:
        filtered = [r for r in filtered if r["age_bucket"] == age_bucket]
    if has_training is not None:
        filtered = [r for r in filtered if r["has_training"] == has_training]
    if has_certification is not None:
        filtered = [r for r in filtered if r["has_certification"] == has_certification]
    if risk_type:
        filtered = [r for r in filtered if _row_matches_risk(r, risk_type, duplicate_iins)]
    if q_name:
        needle = q_name.strip().lower()
        filtered = [r for r in filtered if needle in r["full_name"].lower()]
    if q_position:
        needle = q_position.strip().lower()
        filtered = [r for r in filtered if needle in r["position_raw"].lower()]

    total = len(filtered)
    page = filtered[offset : offset + limit]
    items = [
        {
            "row_id": r["row_id"],
            "full_name": r["full_name"],
            "iin_masked": r["iin_masked"],
            "birth_date": r["birth_date"],
            "age": r["age"],
            "department": r["department"],
            "position_raw": r["position_raw"],
            "training_raw": r["training_raw"][:80] + ("…" if len(r["training_raw"]) > 80 else "")
            if r["training_raw"]
            else "",
            "certification_raw": r["certification_raw"][:80]
            + ("…" if len(r["certification_raw"]) > 80 else "")
            if r["certification_raw"]
            else "",
            "source_sheet": r["source_sheet"],
            "source_row_number": r["source_row_number"],
            "sheet_type": r["sheet_type"],
            "classification": r["classification"],
            "row_type": r.get("row_type", ""),
            "declaration_group": r.get("declaration_group", ""),
            "is_employee_roster": r.get("is_employee_roster", False),
        }
        for r in page
    ]
    return {"batch_id": batch_id, "total": total, "limit": limit, "offset": offset, "items": items}
