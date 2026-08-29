"""Read-only personnel reports built from the operational personnel contour."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import re
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


NOT_SPECIFIED = "Не указано"


def list_report_org_options(
    engine: Engine,
    *,
    scope_unit_ids: list[int] | None,
) -> dict[str, list[dict[str, Any]]]:
    params: dict[str, Any] = {}
    scope_sql = ""
    if scope_unit_ids is not None:
        if not scope_unit_ids:
            return {"groups": [], "departments": []}
        scope_sql = "AND ou.unit_id = ANY(:scope_unit_ids)"
        params["scope_unit_ids"] = list(scope_unit_ids)

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT ou.unit_id, ou.name AS unit_name, ou.group_id,
                       COALESCE(dg.group_name, 'Группа #' || ou.group_id::text) AS group_name
                FROM public.org_units ou
                LEFT JOIN public.deps_group dg ON dg.group_id = ou.group_id
                WHERE COALESCE(ou.is_active, TRUE) = TRUE
                  AND ou.group_id IS NOT NULL
                  {scope_sql}
                ORDER BY LOWER(COALESCE(dg.group_name, '')), LOWER(ou.name), ou.unit_id
                """
            ),
            params,
        ).mappings().all()

    departments = [
        {
            "unit_id": int(row["unit_id"]),
            "unit_name": str(row["unit_name"]),
            "group_id": int(row["group_id"]),
        }
        for row in rows
    ]
    group_names: dict[int, str] = {}
    for row in rows:
        group_names.setdefault(int(row["group_id"]), str(row["group_name"]))
    groups = [
        {"group_id": group_id, "group_name": group_names[group_id]}
        for group_id in sorted(group_names, key=lambda value: group_names[value].casefold())
    ]
    return {"groups": groups, "departments": departments}


def assert_report_org_unit_accessible(
    conn: Connection,
    *,
    org_unit_id: int,
    scope_unit_ids: list[int] | None,
) -> dict[str, Any] | None:
    if scope_unit_ids is not None and org_unit_id not in scope_unit_ids:
        return None
    row = conn.execute(
        text(
            """
            SELECT ou.unit_id, ou.name AS unit_name, ou.group_id,
                   COALESCE(dg.group_name, 'Группа #' || ou.group_id::text) AS group_name
            FROM public.org_units ou
            LEFT JOIN public.deps_group dg ON dg.group_id = ou.group_id
            WHERE ou.unit_id = :org_unit_id
              AND COALESCE(ou.is_active, TRUE) = TRUE
              AND ou.group_id IS NOT NULL
            """
        ),
        {"org_unit_id": int(org_unit_id)},
    ).mappings().first()
    return dict(row) if row else None


def build_personnel_roster(
    engine: Engine,
    *,
    org_unit: dict[str, Any],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the single source of truth used by both preview and Excel."""
    formed_at = generated_at or datetime.now(timezone.utc)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT COALESCE(NULLIF(BTRIM(p.full_name), ''), NULLIF(BTRIM(e.full_name), '')) AS full_name,
                       NULLIF(BTRIM(pos.name), '') AS position_name,
                       pa.rate
                FROM public.employees e
                JOIN public.persons p ON p.person_id = e.person_id
                JOIN public.person_assignments pa
                  ON pa.person_id = e.person_id
                 AND pa.org_unit_id = :org_unit_id
                 AND pa.active_flag IS TRUE
                 AND pa.is_primary IS TRUE
                 AND pa.lifecycle_status = 'active'
                 AND pa.start_date <= CURRENT_DATE
                 AND (pa.end_date IS NULL OR pa.end_date >= CURRENT_DATE)
                LEFT JOIN public.positions pos ON pos.position_id = pa.position_id
                WHERE COALESCE(e.is_active, TRUE) IS TRUE
                  AND e.operational_status = 'active'
                  AND COALESCE(e.date_from, CURRENT_DATE) <= CURRENT_DATE
                  AND (e.date_to IS NULL OR e.date_to >= CURRENT_DATE)
                  AND COALESCE(p.person_status, 'active') = 'active'
                ORDER BY LOWER(COALESCE(NULLIF(BTRIM(p.full_name), ''), NULLIF(BTRIM(e.full_name), ''))),
                         COALESCE(NULLIF(BTRIM(p.full_name), ''), NULLIF(BTRIM(e.full_name), '')),
                         e.employee_id
                """
            ),
            {"org_unit_id": int(org_unit["unit_id"])},
        ).mappings().all()

    items: list[dict[str, Any]] = []
    for number, row in enumerate(rows, start=1):
        rate = row.get("rate")
        items.append(
            {
                "number": number,
                "full_name": str(row.get("full_name") or NOT_SPECIFIED),
                "position": str(row.get("position_name") or NOT_SPECIFIED),
                "rate": _format_rate(rate) if rate is not None else NOT_SPECIFIED,
            }
        )
    return {
        "report_code": "personnel_roster",
        "report_name": "Личный состав",
        "generated_at": formed_at.isoformat(),
        "group": {"id": int(org_unit["group_id"]), "name": str(org_unit["group_name"])},
        "department": {"id": int(org_unit["unit_id"]), "name": str(org_unit["unit_name"])},
        "items": items,
    }


def _format_rate(value: Any) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def build_personnel_roster_xlsx(report: dict[str, Any]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Личный состав"
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:D1")
    ws["A1"] = report["report_name"]
    ws["A1"].font = Font(bold=True, size=16)
    ws["A1"].alignment = Alignment(horizontal="center")
    ws["A3"] = "Группа отделений"
    ws["B3"] = report["group"]["name"]
    ws["A4"] = "Отделение"
    ws["B4"] = report["department"]["name"]
    ws["A5"] = "Дата и время формирования"
    ws["B5"] = datetime.fromisoformat(report["generated_at"]).astimezone().strftime("%d.%m.%Y %H:%M")

    header_row = 7
    headers = ("№", "ФИО", "Должность", "Ставка")
    for column, value in enumerate(headers, start=1):
        cell = ws.cell(header_row, column, value)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2563EB")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_number, item in enumerate(report["items"], start=header_row + 1):
        values: Iterable[Any] = (item["number"], item["full_name"], item["position"], item["rate"])
        for column, value in enumerate(values, start=1):
            cell = ws.cell(row_number, column, value)
            cell.alignment = Alignment(
                horizontal="center" if column in (1, 4) else "left",
                vertical="top",
                wrap_text=True,
            )

    widths = (7, 38, 38, 12)
    for column, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(column)].width = width
    ws.freeze_panes = f"A{header_row + 1}"
    ws.print_title_rows = f"{header_row}:{header_row}"
    ws.page_setup.orientation = "portrait"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_area = f"A1:D{max(header_row, header_row + len(report['items']))}"

    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()


def roster_filename(report: dict[str, Any]) -> str:
    department = re.sub(r"[^\w\-.]+", "_", str(report["department"]["name"]), flags=re.UNICODE).strip("_")
    date_part = datetime.fromisoformat(report["generated_at"]).strftime("%Y-%m-%d")
    return f"Личный_состав_{department or 'отделение'}_{date_part}.xlsx"
