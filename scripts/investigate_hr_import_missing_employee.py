#!/usr/bin/env python3
"""Investigate where an employee was lost in the HR import pipeline (ADR-039/040).

Usage:
  python scripts/investigate_hr_import_missing_employee.py --batch-id 4 --iin 800115300290
  python scripts/investigate_hr_import_missing_employee.py --batch-id 4 --iin 800115300290 --xlsx "/path/контрольный июнь.xlsx"
  python scripts/investigate_hr_import_missing_employee.py --batch-id 4 --iin 800115300290 --full-name "Әбитаев Ерхан Сайлаубекулы"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.hr_import_analytics_service import is_real_employee_row
from scripts.diagnose_hr_import_batch_bindings import _table_column_names, fetch_batch_header
from scripts.import_hr_control_list import infer_row_type, looks_like_person_name, parse_workbook

DEFAULT_NAME_VARIANTS = (
    "Әбитаев",
    "Абитаев",
    "Ерхан",
    "Сайлаубекулы",
)


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str, indent=2)


def _snapshot_batch_filter(conn: Connection, batch_id: int) -> tuple[str, dict[str, Any]]:
    columns = _table_column_names(conn, "hr_canonical_snapshots")
    if "source_batch_id" in columns:
        return "source_batch_id = :batch_id", {"batch_id": batch_id}
    if "batch_id" in columns:
        return "batch_id = :batch_id", {"batch_id": batch_id}
    return "FALSE", {}


def _snapshot_batch_join_filter(conn: Connection, batch_id: int) -> tuple[str, dict[str, Any]]:
    columns = _table_column_names(conn, "hr_canonical_snapshots")
    if "source_batch_id" in columns:
        return "s.source_batch_id = :batch_id", {"batch_id": batch_id}
    if "batch_id" in columns:
        return "s.batch_id = :batch_id", {"batch_id": batch_id}
    return "FALSE", {}


def _table_exists(conn: Connection, table_name: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table_name
                """
            ),
            {"table_name": table_name},
        ).first()
    )


def _search_import_rows(
    conn: Connection,
    *,
    batch_id: int,
    iin_digits: str,
    name_variants: list[str],
) -> list[dict[str, Any]]:
    clauses = ["batch_id = :batch_id"]
    params: dict[str, Any] = {"batch_id": batch_id}

    iin_checks = []
    if iin_digits:
        iin_checks.append(
            """
            regexp_replace(COALESCE(normalized_payload->>'iin', ''), '[^0-9]', '', 'g') = :iin_digits
            OR regexp_replace(COALESCE(raw_payload->>'iin', ''), '[^0-9]', '', 'g') = :iin_digits
            """
        )
        params["iin_digits"] = iin_digits

    name_checks = []
    for idx, variant in enumerate(name_variants):
        key = f"name_{idx}"
        name_checks.append(
            f"lower(COALESCE(normalized_payload->>'full_name', '')) LIKE :{key}"
        )
        name_checks.append(f"lower(COALESCE(raw_payload->>'full_name', '')) LIKE :{key}")
        params[key] = f"%{variant.strip().lower()}%"

    if iin_checks or name_checks:
        match_parts = []
        if iin_checks:
            match_parts.append(f"({' OR '.join(iin_checks)})")
        if name_checks:
            match_parts.append(f"({' OR '.join(name_checks)})")
        clauses.append(f"({' OR '.join(match_parts)})")

    sql = f"""
        SELECT
            row_id,
            source_sheet,
            source_row_number,
            match_status,
            review_status,
            error_codes,
            employee_id,
            normalized_payload,
            raw_payload
        FROM public.hr_import_rows
        WHERE {' AND '.join(clauses)}
        ORDER BY row_id
    """
    rows = conn.execute(text(sql), params).mappings().all()
    return [dict(row) for row in rows]


def _serialize_import_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row.get("normalized_payload") or {})
    metadata = dict(payload.get("metadata") or {})
    analytics_row = {
        "sheet_type": metadata.get("sheet_type"),
        "classification": metadata.get("classification"),
        "row_type": metadata.get("row_type"),
        "is_employee_roster": metadata.get("is_employee_roster"),
        "full_name": payload.get("full_name"),
        "iin": payload.get("iin"),
        "employee_number": payload.get("employee_number"),
        "source_type": "HR_CONTROL_LIST",
    }
    return {
        "row_id": int(row["row_id"]),
        "source_sheet": row.get("source_sheet"),
        "source_row_number": row.get("source_row_number"),
        "match_status": row.get("match_status"),
        "review_status": row.get("review_status"),
        "error_codes": row.get("error_codes"),
        "employee_id": row.get("employee_id"),
        "full_name": payload.get("full_name"),
        "iin": payload.get("iin"),
        "metadata": metadata,
        "is_real_employee_row": is_real_employee_row(analytics_row),
        "profile_status": row.get("profile_status") if "profile_status" in row else None,
        "diff_status": row.get("diff_status") if "diff_status" in row else None,
    }


def _lookup_employee_registry(conn: Connection, iin_digits: str) -> list[dict[str, Any]]:
    if not iin_digits:
        return []
    rows = conn.execute(
        text(
            """
            SELECT
                e.employee_id,
                e.full_name,
                ei.identity_value AS iin,
                e.is_active
            FROM public.employee_identities ei
            JOIN public.employees e ON e.employee_id = ei.employee_id
            WHERE ei.identity_type = 'IIN'
              AND ei.valid_to IS NULL
              AND regexp_replace(COALESCE(ei.identity_value, ''), '[^0-9]', '', 'g') = :iin_digits
            ORDER BY ei.is_primary DESC, e.employee_id
            """
        ),
        {"iin_digits": iin_digits},
    ).mappings().all()
    return [dict(row) for row in rows]


def _normalized_records_for_rows(
    conn: Connection,
    *,
    batch_id: int,
    row_ids: list[int],
    iin_digits: str,
) -> list[dict[str, Any]]:
    if not _table_exists(conn, "hr_import_normalized_records"):
        return []
    params: dict[str, Any] = {"batch_id": batch_id}
    row_filter = ""
    if row_ids:
        row_filter = "AND nr.row_id = ANY(:row_ids)"
        params["row_ids"] = row_ids
    iin_filter = ""
    if iin_digits:
        iin_filter = """
            AND regexp_replace(COALESCE(r.normalized_payload->>'iin', ''), '[^0-9]', '', 'g')
                LIKE :iin_pattern
        """
        params["iin_pattern"] = f"%{iin_digits}%"

    rows = conn.execute(
        text(
            f"""
            SELECT
                nr.normalized_record_id,
                nr.row_id,
                nr.employee_id,
                nr.record_kind,
                nr.document_type_code,
                nr.review_status,
                nr.source_record_key
            FROM public.hr_import_normalized_records nr
            JOIN public.hr_import_rows r ON r.row_id = nr.row_id
            WHERE nr.batch_id = :batch_id
            {row_filter}
            {iin_filter}
            ORDER BY nr.normalized_record_id
            """
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def _snapshot_batch_select_expr(conn: Connection) -> str:
    columns = _table_column_names(conn, "hr_canonical_snapshots")
    if "source_batch_id" in columns:
        return "s.source_batch_id"
    if "batch_id" in columns:
        return "s.batch_id"
    return "NULL"


def _canonical_snapshot_entries(
    conn: Connection,
    *,
    iin_digits: str,
    row_ids: list[int],
) -> list[dict[str, Any]]:
    if not _table_exists(conn, "hr_canonical_snapshot_entries"):
        return []

    params: dict[str, Any] = {}
    filters = []
    if iin_digits:
        filters.append(
            "regexp_replace(COALESCE(e.iin, ''), '[^0-9]', '', 'g') = :iin_digits"
        )
        params["iin_digits"] = iin_digits
    if row_ids:
        filters.append("e.source_row_id = ANY(:row_ids)")
        params["row_ids"] = row_ids
    if not filters:
        return []

    batch_col = _snapshot_batch_select_expr(conn)
    rows = conn.execute(
        text(
            f"""
            SELECT
                e.entry_id,
                e.snapshot_id,
                {batch_col} AS batch_id,
                s.status AS snapshot_status,
                e.record_kind,
                e.employee_id,
                e.iin,
                e.source_row_id,
                e.source_normalized_record_id,
                e.match_key
            FROM public.hr_canonical_snapshot_entries e
            JOIN public.hr_canonical_snapshots s ON s.snapshot_id = e.snapshot_id
            WHERE {' OR '.join(filters)}
            ORDER BY e.snapshot_id DESC, e.entry_id
            """
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def _batch_coverage(conn: Connection, batch_id: int) -> dict[str, Any]:
    import_rows = int(
        conn.execute(
            text("SELECT COUNT(*) FROM public.hr_import_rows WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        ).scalar_one()
    )
    roster_rows = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                  AND COALESCE(normalized_payload->'metadata'->>'row_type', '') = 'EMPLOYEE'
                """
            ),
            {"batch_id": batch_id},
        ).scalar_one()
    )
    normalized_rows = 0
    if _table_exists(conn, "hr_import_normalized_records"):
        normalized_rows = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.hr_import_normalized_records
                    WHERE batch_id = :batch_id
                    """
                ),
                {"batch_id": batch_id},
            ).scalar_one()
        )
    snapshot_entries = 0
    snapshots = 0
    if _table_exists(conn, "hr_canonical_snapshots"):
        batch_filter, batch_params = _snapshot_batch_filter(conn, batch_id)
        snapshots = int(
            conn.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM public.hr_canonical_snapshots
                    WHERE {batch_filter}
                    """
                ),
                batch_params,
            ).scalar_one()
        )
    if _table_exists(conn, "hr_canonical_snapshot_entries") and _table_exists(
        conn, "hr_canonical_snapshots"
    ):
        batch_filter, batch_params = _snapshot_batch_join_filter(conn, batch_id)
        snapshot_entries = int(
            conn.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM public.hr_canonical_snapshot_entries e
                    JOIN public.hr_canonical_snapshots s ON s.snapshot_id = e.snapshot_id
                    WHERE {batch_filter}
                    """
                ),
                batch_params,
            ).scalar_one()
        )
    return {
        "hr_import_rows": import_rows,
        "roster_employee_rows": roster_rows,
        "normalized_records": normalized_rows,
        "canonical_snapshots": snapshots,
        "canonical_snapshot_entries": snapshot_entries,
    }


def _audit_excel(path: Path, *, iin_digits: str, name_variants: list[str]) -> dict[str, Any]:
    parsed_rows, warnings = parse_workbook(path)
    employee_like_rows = []
    target_rows = []
    for row in parsed_rows:
        full_name = row.data.get("full_name", "")
        row_iin = row.iin_digits
        inferred = infer_row_type(
            full_name=full_name,
            sheet_type=row.sheet_type,
            iin_digits=row_iin,
        )
        item = {
            "source_sheet": row.data.get("source_sheet"),
            "source_row_number": row.data.get("source_row_number"),
            "full_name": full_name,
            "iin": row_iin,
            "row_type": row.row_type,
            "is_employee_roster": row.is_employee_roster,
            "looks_like_person_name": looks_like_person_name(full_name),
            "infer_row_type": {
                "row_type": inferred[0],
                "is_employee_roster": inferred[1],
            },
            "errors": row.errors,
        }
        if row.is_employee_roster:
            employee_like_rows.append(item)
        if (iin_digits and row_iin == iin_digits) or any(
            variant.lower() in full_name.lower() for variant in name_variants if variant
        ):
            target_rows.append(item)

    return {
        "excel_path": str(path),
        "parsed_rows_total": len(parsed_rows),
        "employee_roster_rows_in_excel": len(employee_like_rows),
        "warnings": warnings,
        "target_rows": target_rows,
        "target_rows_missing_from_db_hint": (
            "Compare target_rows source_row_number with hr_import_rows.source_row_number"
        ),
    }


def _normalization_skip_reason(row_summary: dict[str, Any]) -> str:
    metadata = row_summary.get("metadata") or {}
    row_type = str(metadata.get("row_type") or "")
    if row_summary.get("is_real_employee_row"):
        return "row is eligible for normalization"
    if row_type == "CATEGORY_ROW":
        return (
            "skipped in _load_rows_for_population() because is_real_employee_row() is False: "
            "row_type=CATEGORY_ROW from infer_row_type() / looks_like_person_name()"
        )
    if metadata.get("is_employee_roster") is False:
        return (
            "skipped in _load_rows_for_population() because metadata.is_employee_roster=False"
        )
    return "skipped in _load_rows_for_population() because is_real_employee_row() is False"


def _parser_root_cause(full_name: str, *, sheet_type: str = "doctors", iin_digits: str = "") -> dict[str, Any]:
    row_type, is_employee_roster = infer_row_type(
        full_name=full_name,
        sheet_type=sheet_type,
        iin_digits=iin_digits,
    )
    return {
        "full_name": full_name,
        "looks_like_person_name": looks_like_person_name(full_name),
        "infer_row_type": {
            "row_type": row_type,
            "is_employee_roster": is_employee_roster,
        },
        "code_path": (
            "scripts/import_hr_control_list.py: infer_row_type() uses valid IIN + multi-word FIO "
            "and Kazakh-extended looks_like_person_name()"
        ),
    }


def determine_verdict(
    *,
    import_rows: list[dict[str, Any]],
    normalized_records: list[dict[str, Any]],
    canonical_entries: list[dict[str, Any]],
    registry_employees: list[dict[str, Any]],
    parser_audit: dict[str, Any] | None,
) -> dict[str, Any]:
    if not import_rows:
        return {
            "stage": "lost_before_hr_import_rows",
            "summary": "ИИН/ФИО не найдены в hr_import_rows batch — потеря на этапе Excel parsing/import.",
        }

    row_summaries = [_serialize_import_row(row) for row in import_rows]
    category_rows = [
        row for row in row_summaries if (row.get("metadata") or {}).get("row_type") == "CATEGORY_ROW"
    ]

    if category_rows and not normalized_records:
        parser_hint = None
        if parser_audit and parser_audit.get("target_rows"):
            first = parser_audit["target_rows"][0]
            if not first.get("looks_like_person_name"):
                parser_hint = _parser_root_cause(
                    str(first.get("full_name") or ""),
                    iin_digits=str(first.get("iin") or ""),
                )
        return {
            "stage": "lost_between_hr_import_rows_and_normalized_records",
            "summary": (
                "Запись есть в hr_import_rows, но отсутствует в hr_import_normalized_records. "
                "Вероятная причина: row_type=CATEGORY_ROW / is_employee_roster=false."
            ),
            "normalization_skip_reason": _normalization_skip_reason(category_rows[0]),
            "parser_audit": parser_hint,
        }

    if normalized_records and not canonical_entries:
        return {
            "stage": "lost_between_normalized_records_and_snapshot",
            "summary": (
                "Есть normalized records, но нет canonical_snapshot_entries — "
                "проверьте review_status/promotion/snapshot materialization."
            ),
        }

    if import_rows and normalized_records and registry_employees:
        return {
            "stage": "present_end_to_end",
            "summary": "Запись найдена в import rows, normalized records и employee registry.",
        }

    if import_rows and not normalized_records and canonical_entries:
        return {
            "stage": "partial_path",
            "summary": "Нестандартный путь: import row и snapshot entry без normalized records.",
        }

    return {
        "stage": "ui_search_or_binding_only",
        "summary": (
            "Данные могут существовать, но не находиться из-за UI-фильтров (ФИО/ИИН) "
            "или отсутствия employee binding."
        ),
    }


def investigate_missing_employee(
    *,
    batch_id: int,
    iin: str,
    full_name: str | None = None,
    xlsx_path: Path | None = None,
    name_variants: list[str] | None = None,
) -> dict[str, Any]:
    iin_digits = _digits_only(iin)
    variants = list(name_variants or [])
    for value in (full_name, *DEFAULT_NAME_VARIANTS):
        if value and value not in variants:
            variants.append(value)

    report: dict[str, Any] = {
        "batch_id": batch_id,
        "iin": iin_digits,
        "name_variants": variants,
    }

    with engine.connect() as conn:
        report["batch"] = fetch_batch_header(conn, batch_id)
        report["coverage"] = _batch_coverage(conn, batch_id)
        report["employee_registry"] = _lookup_employee_registry(conn, iin_digits)

        import_rows = _search_import_rows(
            conn,
            batch_id=batch_id,
            iin_digits=iin_digits,
            name_variants=variants,
        )
        report["hr_import_rows"] = {
            "count": len(import_rows),
            "items": [_serialize_import_row(row) for row in import_rows],
        }

        row_ids = [int(row["row_id"]) for row in import_rows]
        normalized_records = _normalized_records_for_rows(
            conn,
            batch_id=batch_id,
            row_ids=row_ids,
            iin_digits=iin_digits,
        )
        report["hr_import_normalized_records"] = {
            "count": len(normalized_records),
            "items": normalized_records,
        }
        report["canonical_snapshot_entries"] = {
            "count": len(
                entries := _canonical_snapshot_entries(
                    conn,
                    iin_digits=iin_digits,
                    row_ids=row_ids,
                )
            ),
            "items": entries,
        }

    if xlsx_path is not None:
        report["excel_audit"] = _audit_excel(xlsx_path, iin_digits=iin_digits, name_variants=variants)

    if full_name:
        report["parser_root_cause"] = _parser_root_cause(full_name, iin_digits=iin_digits)

    report["verdict"] = determine_verdict(
        import_rows=import_rows,
        normalized_records=normalized_records,
        canonical_entries=report["canonical_snapshot_entries"]["items"],
        registry_employees=report["employee_registry"],
        parser_audit=report.get("excel_audit"),
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Investigate missing employee in HR import pipeline")
    parser.add_argument("--batch-id", type=int, required=True)
    parser.add_argument("--iin", type=str, required=True)
    parser.add_argument("--full-name", type=str, default=None)
    parser.add_argument("--xlsx", type=str, default=None)
    parser.add_argument("--name-variant", action="append", default=[])
    args = parser.parse_args()

    report = investigate_missing_employee(
        batch_id=args.batch_id,
        iin=args.iin,
        full_name=args.full_name,
        xlsx_path=Path(args.xlsx) if args.xlsx else None,
        name_variants=args.name_variant or None,
    )
    print(_json(report))


if __name__ == "__main__":
    main()
