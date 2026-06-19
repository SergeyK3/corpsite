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
from app.services.department_recoding_service import load_org_unit_group_ids, lookup_recoding
from app.services.hr_import_document_parser import parse_certification_raw

MEDICAL_CATEGORY_KEYS = frozenset({"highest", "first", "second"})

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


def _format_category_date(value: Optional[date]) -> str:
    if not value:
        return ""
    if value.month == 1 and value.day == 1 and value.year >= 1900:
        return str(value.year)
    return value.isoformat()


CATEGORY_VALIDITY_TERM_YEARS = 5
CATEGORY_VALIDITY_EXPIRED_NOTE = "утратила силу"


def _parse_category_issued_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4}", text):
        return date(int(text), 1, 1)
    dmy_match = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if dmy_match:
        return date(int(dmy_match.group(3)), int(dmy_match.group(2)), int(dmy_match.group(1)))
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _calc_years_between(from_d: date, to_d: date) -> float:
    days = (to_d - from_d).days
    if days < 0:
        return 0.0
    return round((days / 365.25) * 10) / 10


def _format_validity_years_decimal(years: float) -> str:
    normalized = max(0.0, years)
    int_part = int(normalized)
    dec_part = round((normalized - int_part) * 10)
    return f"{int_part},{dec_part}"


def calc_record_validity_note(issued_at: Any, *, on: Optional[date] = None) -> str:
    from_d = _parse_category_issued_date(issued_at)
    if not from_d:
        return ""
    today = on or date.today()
    elapsed = _calc_years_between(from_d, today)
    if elapsed > CATEGORY_VALIDITY_TERM_YEARS:
        return CATEGORY_VALIDITY_EXPIRED_NOTE
    remaining = max(0.0, CATEGORY_VALIDITY_TERM_YEARS - elapsed)
    return f"осталось {_format_validity_years_decimal(remaining)} лет"


def calc_category_validity_note(issued_at: Any, *, on: Optional[date] = None) -> str:
    return calc_record_validity_note(issued_at, on=on)


def _resolve_medical_category_key(category: Optional[str], raw_text: str) -> str:
    cat = (category or "").strip().lower()
    if cat in MEDICAL_CATEGORY_KEYS:
        return cat
    text_val = (raw_text or "").lower()
    if "высш" in text_val:
        return "highest"
    if "перва" in text_val:
        return "first"
    if "втор" in text_val:
        return "second"
    return ""


def _medical_category_entries(certification_raw: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for frag in parse_certification_raw(certification_raw):
        if frag.proposed_document_type != "QUALIFICATION_CATEGORY":
            continue
        category_key = _resolve_medical_category_key(frag.category, frag.raw_text)
        if not category_key:
            continue
        specialty = (frag.specialty or "").strip()
        title = (frag.title or "").strip()
        if not specialty and title and category_key not in title.lower():
            specialty = title
        entries.append(
            {
                "category": category_key,
                "date": frag.parsed_issued_at or frag.parsed_valid_until,
                "specialty": specialty,
            }
        )
    return entries


def _latest_medical_category(certification_raw: str) -> tuple[str, str]:
    entries = _medical_category_entries(certification_raw)
    if not entries:
        return "none", ""
    dated = [entry for entry in entries if entry["date"]]
    latest = max(dated, key=lambda entry: entry["date"]) if dated else entries[-1]
    return str(latest["category"]), _format_category_date(latest["date"])


def _infer_staff_type(row: dict[str, Any]) -> str:
    """Map row to personnel staff bucket (part_time is a flag, not a bucket)."""
    sheet_type = str(row.get("sheet_type") or "")
    if sheet_type in ("doctors", "nurses", "junior_staff", "other_staff"):
        return sheet_type
    declaration_group = str(row.get("declaration_group") or "")
    if declaration_group in ("doctors", "nurses", "junior_staff", "other_staff"):
        return declaration_group
    position = str(row.get("position_raw") or "").lower()
    if any(k in position for k in ("врач", "доктор", "ординатор")):
        return "doctors"
    if any(k in position for k in ("медсестр", "смр", "м/с", "фельдшер")):
        return "nurses"
    if any(k in position for k in ("санитар", "уборщ", "прач")):
        return "junior_staff"
    return "other_staff"


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


def _norm_person_name(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("ё", "е").split())


def _build_roster_department_index(
    items: list[dict[str, Any]],
) -> tuple[dict[tuple[str, str], str], dict[str, str], dict[str, str]]:
    """Index employee roster departments by (iin, name), iin alone, and name alone."""
    by_iin_name: dict[tuple[str, str], str] = {}
    by_iin: dict[str, str] = {}
    by_name: dict[str, str] = {}
    for row in items:
        if not is_real_employee_row(row):
            continue
        dept = str(row.get("department") or "").strip()
        if not dept:
            continue
        iin = str(row.get("iin") or "").strip()
        name_key = _norm_person_name(str(row.get("full_name") or ""))
        if iin and name_key:
            by_iin_name[(iin, name_key)] = dept
        if iin and iin not in by_iin:
            by_iin[iin] = dept
        if name_key and name_key not in by_name:
            by_name[name_key] = dept
    return by_iin_name, by_iin, by_name


def _resolve_declaration_department(
    row: dict[str, Any],
    *,
    by_iin_name: dict[tuple[str, str], str],
    by_iin: dict[str, str],
    by_name: dict[str, str],
) -> str:
    """Fill missing declaration department from matching employee roster row."""
    existing = str(row.get("department") or "").strip()
    if existing:
        return existing
    iin = str(row.get("iin") or "").strip()
    name_key = _norm_person_name(str(row.get("full_name") or ""))
    if iin and name_key and (iin, name_key) in by_iin_name:
        return by_iin_name[(iin, name_key)]
    if iin and iin in by_iin:
        return by_iin[iin]
    if name_key and name_key in by_name:
        return by_name[name_key]
    return ""


def _enrich_declaration_departments(items: list[dict[str, Any]]) -> None:
    roster_by_iin_name, roster_by_iin, roster_by_name = _build_roster_department_index(items)
    for item in items:
        if not is_declaration_row(item):
            continue
        item["department"] = _resolve_declaration_department(
            item,
            by_iin_name=roster_by_iin_name,
            by_iin=roster_by_iin,
            by_name=roster_by_name,
        )


def _canonical_department_label(row: dict[str, Any]) -> str:
    """Group/filter key: canonical org unit name after recoding, else raw import name."""
    canonical = str(row.get("org_unit_name") or "").strip()
    if canonical:
        return canonical
    return row.get("department") or "— не указано —"


def is_missing_iin_employee_row(row: dict[str, Any]) -> bool:
    return is_real_employee_row(row) and not row.get("iin")


def _ensure_batch_exists(conn: Connection, batch_id: int) -> None:
    row = conn.execute(
        text("SELECT 1 FROM public.hr_import_batches WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    ).first()
    if not row:
        raise BatchNotFoundError(f"batch_id={batch_id} not found")


def load_row_payload(conn: Connection, batch_id: int, row_id: int) -> dict[str, Any]:
    _ensure_batch_exists(conn, batch_id)
    db_row = conn.execute(
        text(
            """
            SELECT row_id, source_sheet, source_row_number, normalized_payload, employee_id
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id AND row_id = :row_id
            """
        ),
        {"batch_id": batch_id, "row_id": row_id},
    ).mappings().first()
    if not db_row:
        raise BatchNotFoundError(f"row_id={row_id} not found in batch {batch_id}")
    payload = dict(db_row["normalized_payload"] or {})
    metadata = dict(payload.pop("metadata", {}) or {})
    return {
        "row_id": int(db_row["row_id"]),
        "source_sheet": str(db_row["source_sheet"] or ""),
        "source_row_number": int(db_row["source_row_number"]),
        "employee_id": int(db_row["employee_id"]) if db_row["employee_id"] else None,
        "payload": payload,
        "metadata": metadata,
    }


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
        is_part_time = bool(
            metadata.get("is_part_time", False) or sheet_type == "part_time"
        )
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
                "education_raw": str(payload.get("education_raw", "") or "").strip(),
                "experience_raw": str(payload.get("experience_raw", "") or "").strip(),
                "degree_raw": str(payload.get("degree_raw", "") or "").strip(),
                "awards_raw": str(payload.get("awards_raw", "") or "").strip(),
                "note_raw": str(payload.get("note_raw", "") or "").strip(),
                "sheet_type": sheet_type,
                "classification": classification,
                "row_type": row_type,
                "declaration_group": declaration_group,
                "is_employee_roster": is_employee_roster,
                "is_part_time": is_part_time,
                "staff_type": _infer_staff_type(
                    {
                        "sheet_type": sheet_type,
                        "declaration_group": declaration_group,
                        "position_raw": str(payload.get("position_raw", "") or ""),
                    }
                ),
                "error_codes": list(db_row["error_codes"] or []),
                "has_training": bool(str(payload.get("training_raw", "") or "").strip()),
                "has_certification": bool(str(payload.get("certification_raw", "") or "").strip()),
            }
        )
        latest_category, latest_category_date = _latest_medical_category(items[-1]["certification_raw"])
        items[-1]["latest_medical_category"] = latest_category
        items[-1]["latest_medical_category_date"] = latest_category_date
    _enrich_declaration_departments(items)
    org_unit_group_ids = load_org_unit_group_ids(conn)
    recoding_cache: dict[str, Optional[dict[str, Any]]] = {}
    for item in items:
        dept = item["department"]
        if dept not in recoding_cache:
            recoding_cache[dept] = lookup_recoding(conn, dept)
        rec = recoding_cache[dept]
        org_unit_id = int(rec["org_unit_id"]) if rec and rec.get("org_unit_id") else None
        item["org_unit_id"] = org_unit_id
        item["org_unit_name"] = rec["org_unit_name"] if rec else ""
        item["department_group"] = rec["department_group"] if rec else ""
        item["org_group_id"] = org_unit_group_ids.get(org_unit_id) if org_unit_id else None
    return items


def _normalized_records_table_exists(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'hr_import_normalized_records'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def list_batches(
    conn: Connection,
    *,
    with_normalized_record_count: bool = False,
) -> dict[str, Any]:
    if with_normalized_record_count and _normalized_records_table_exists(conn):
        rows = conn.execute(
            text(
                """
                SELECT
                    b.batch_id,
                    b.file_name,
                    b.imported_at,
                    b.status,
                    b.total_rows,
                    b.valid_rows,
                    b.error_rows,
                    COALESCE(nr.normalized_record_count, 0) AS normalized_record_count
                FROM public.hr_import_batches b
                LEFT JOIN (
                    SELECT batch_id, COUNT(*)::int AS normalized_record_count
                    FROM public.hr_import_normalized_records
                    GROUP BY batch_id
                ) nr ON nr.batch_id = b.batch_id
                ORDER BY b.imported_at DESC, b.batch_id DESC
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
                    "normalized_record_count": int(r["normalized_record_count"]),
                }
                for r in rows
            ]
        }

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
                **(
                    {"normalized_record_count": 0}
                    if with_normalized_record_count
                    else {}
                ),
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
        dept = _canonical_department_label(row)
        bucket = grouped.setdefault(
            dept,
            {
                "department": dept,
                "org_unit_id": row.get("org_unit_id"),
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
    by_department = Counter(_canonical_department_label(r) for r in with_training)
    by_staff_type = Counter(r["sheet_type"] or "other_staff" for r in with_training)

    dept_totals = Counter(_canonical_department_label(r) for r in employee_rows)
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
    by_department = Counter(_canonical_department_label(r) for r in with_cert)

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
    department_group: Optional[str] = None,
    org_group_id: Optional[int] = None,
    org_unit_id: Optional[int] = None,
    org_unit_name: Optional[str] = None,
    certification_category: Optional[str] = None,
    staff_type: Optional[str] = None,
    staff_types: Optional[str] = None,
    part_time: Optional[str] = None,
    hide_unchanged: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    rows = _load_staging_rows(conn, batch_id)
    employee_rows = [r for r in rows if is_real_employee_row(r)]
    iin_counts = Counter(r["iin"] for r in employee_rows if r["iin"])
    duplicate_iins = {iin for iin, count in iin_counts.items() if count > 1}

    effective_org_group_id = org_group_id
    if effective_org_group_id is None and department_group:
        try:
            parsed = int(str(department_group).strip())
            if parsed >= 1:
                effective_org_group_id = parsed
        except ValueError:
            pass

    filtered = rows
    if roster_scope:
        filtered = [r for r in filtered if _matches_roster_scope(r, roster_scope)]
    if department:
        filtered = [r for r in filtered if r["department"] == department]
    if effective_org_group_id is not None:
        filtered = [r for r in filtered if r.get("org_group_id") == effective_org_group_id]
    if org_unit_id is not None:
        filtered = [
            r
            for r in filtered
            if r.get("org_unit_id") == org_unit_id
            or (
                org_unit_name
                and (r.get("org_unit_name") or "").strip().lower() == org_unit_name.strip().lower()
            )
        ]
    elif org_unit_name:
        filtered = [
            r
            for r in filtered
            if (r.get("org_unit_name") or "").strip().lower() == org_unit_name.strip().lower()
        ]
    if certification_category:
        use_latest_medical = roster_scope in (None, "personnel", "all")
        if use_latest_medical:
            if certification_category == "none":
                filtered = [
                    r for r in filtered if r.get("latest_medical_category", "none") in ("none", "")
                ]
            else:
                filtered = [
                    r for r in filtered if r.get("latest_medical_category") == certification_category
                ]
        elif certification_category == "none":
            filtered = [r for r in filtered if r.get("certification_group") == "none"]
        else:
            filtered = [
                r for r in filtered if r.get("certification_group") == certification_category
            ]
    if staff_types:
        allowed_staff_types = {part.strip() for part in staff_types.split(",") if part.strip()}
        if allowed_staff_types:
            filtered = [r for r in filtered if r.get("staff_type") in allowed_staff_types]
    if staff_type:
        filtered = [r for r in filtered if r.get("staff_type") == staff_type]
    if part_time == "only":
        filtered = [r for r in filtered if r.get("is_part_time")]
    elif part_time == "exclude":
        filtered = [r for r in filtered if not r.get("is_part_time")]
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

    diff_by_row: dict[int, dict[str, Any]] = {}
    if hide_unchanged:
        try:
            from app.services.hr_import_monthly_diff_service import (
                load_row_diff_fields,
                row_passes_hide_unchanged,
            )

            diff_by_row = load_row_diff_fields(conn, batch_id)
            filtered = [
                r
                for r in filtered
                if row_passes_hide_unchanged(
                    diff_by_row.get(int(r["row_id"]), {}).get("diff_status"),
                    hide_unchanged=True,
                )
            ]
        except Exception:
            diff_by_row = {}

    total = len(filtered)
    page = filtered[offset : offset + limit]
    if not diff_by_row:
        try:
            from app.services.hr_import_monthly_diff_service import load_row_diff_fields

            diff_by_row = load_row_diff_fields(conn, batch_id)
        except Exception:
            diff_by_row = {}
    items = [
        {
            "row_id": r["row_id"],
            "full_name": r["full_name"],
            "iin": r["iin"],
            "birth_date": r["birth_date"],
            "age": r["age"],
            "department": r["department"],
            "org_unit_id": r.get("org_unit_id"),
            "org_unit_name": r.get("org_unit_name", ""),
            "org_group_id": r.get("org_group_id"),
            "department_group": r.get("department_group", ""),
            "position_raw": r["position_raw"],
            "training_raw": r["training_raw"][:80] + ("…" if len(r["training_raw"]) > 80 else "")
            if r["training_raw"]
            else "",
            "certification_raw": r["certification_raw"][:80]
            + ("…" if len(r["certification_raw"]) > 80 else "")
            if r["certification_raw"]
            else "",
            "certification_group": r.get("certification_group", "none"),
            "latest_medical_category": r.get("latest_medical_category", "none"),
            "latest_medical_category_date": r.get("latest_medical_category_date", ""),
            "source_sheet": r["source_sheet"],
            "source_row_number": r["source_row_number"],
            "sheet_type": r["sheet_type"],
            "staff_type": r.get("staff_type", ""),
            "is_part_time": r.get("is_part_time", False),
            "classification": r["classification"],
            "row_type": r.get("row_type", ""),
            "declaration_group": r.get("declaration_group", ""),
            "is_employee_roster": r.get("is_employee_roster", False),
            **diff_by_row.get(int(r["row_id"]), {}),
        }
        for r in page
    ]
    return {
        "batch_id": batch_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "hide_unchanged": hide_unchanged,
        "items": items,
    }


def delete_batch(conn: Connection, batch_id: int) -> dict[str, Any]:
    """Delete import batch; cascades to hr_import_rows and hr_import_document_candidates."""
    _ensure_batch_exists(conn, batch_id)
    row_counts = conn.execute(
        text(
            """
            SELECT
                (SELECT COUNT(*) FROM public.hr_import_rows WHERE batch_id = :batch_id) AS rows,
                (SELECT COUNT(*) FROM public.hr_import_document_candidates WHERE batch_id = :batch_id) AS candidates
            """
        ),
        {"batch_id": batch_id},
    ).mappings().one()
    conn.execute(
        text("DELETE FROM public.hr_import_batches WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    )
    return {
        "batch_id": batch_id,
        "deleted": True,
        "deleted_rows": int(row_counts["rows"]),
        "deleted_candidates": int(row_counts["candidates"]),
    }


def sheet_diagnostics(conn: Connection, batch_id: int) -> dict[str, Any]:
    """Per Excel sheet breakdown — helps explain low row counts after upload."""
    rows = _load_staging_rows(conn, batch_id)
    candidate_counts: dict[str, int] = defaultdict(int)
    cand_rows = conn.execute(
        text(
            """
            SELECT source_sheet, COUNT(*) AS cnt
            FROM public.hr_import_document_candidates
            WHERE batch_id = :batch_id
            GROUP BY source_sheet
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()
    for row in cand_rows:
        candidate_counts[str(row["source_sheet"] or "")] = int(row["cnt"])

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        sheet_name = row["source_sheet"] or "—"
        bucket = grouped.setdefault(
            sheet_name,
            {
                "sheet_name": sheet_name,
                "sheet_type": row["sheet_type"] or "",
                "rows_total": 0,
                "employee_rows": 0,
                "declaration_rows": 0,
                "technical_rows": 0,
                "candidates_count": candidate_counts.get(sheet_name, 0),
            },
        )
        bucket["rows_total"] += 1
        if is_real_employee_row(row):
            bucket["employee_rows"] += 1
        elif is_declaration_row(row):
            bucket["declaration_rows"] += 1
        else:
            bucket["technical_rows"] += 1
        if row["sheet_type"] and not bucket["sheet_type"]:
            bucket["sheet_type"] = row["sheet_type"]

    items = sorted(grouped.values(), key=lambda x: x["sheet_name"])
    return {
        "batch_id": batch_id,
        "items": items,
        "totals": {
            "rows_total": len(rows),
            "employee_rows": sum(1 for r in rows if is_real_employee_row(r)),
            "declaration_rows": sum(1 for r in rows if is_declaration_row(r)),
            "technical_rows": sum(
                1 for r in rows if not is_real_employee_row(r) and not is_declaration_row(r)
            ),
            "candidates_count": sum(candidate_counts.values()),
        },
    }
